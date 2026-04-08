import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'

const SCHEDULE_LABELS = {
  appliances: 'Appliances',
  bath_accessories: 'Bath Accessories',
  cabinetry_hardware: 'Cabinetry Hardware',
  cabinetry_inserts: 'Cabinetry Inserts',
  cabinetry_style_species: 'Cabinetry Style & Species',
  countertops: 'Countertops',
  covering_calculations: 'Covering Calculations',
  decorative_lighting: 'Decorative Lighting',
  door_hardware: 'Door Hardware',
  doors: 'Doors',
  flooring: 'Flooring',
  furniture: 'Furniture',
  lighting_electrical: 'Lighting & Electrical',
  plumbing: 'Plumbing',
  shower_glass_mirrors: 'Shower Glass & Mirrors',
  specialty_equipment: 'Specialty Equipment',
  surface_finishes: 'Surface Finishes',
  tile: 'Tile',
  windows: 'Windows',
}

function Dashboard() {
  const { id } = useParams()
  const [project, setProject] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchProject = () => {
    setLoading(true)
    fetch(`/api/projects/${id}`)
      .then((res) => {
        if (!res.ok) throw new Error('Project not found')
        return res.json()
      })
      .then((data) => {
        setProject(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }

  useEffect(() => {
    fetchProject()
  }, [id])

  if (loading) return <p className="text-warm-gray">Loading...</p>
  if (error) return <p className="text-red-600">{error}</p>
  if (!project) return <p className="text-warm-gray">Project not found.</p>

  const schedules = project.schedules || {}

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to="/" className="text-olive hover:underline text-sm font-heading mb-1 inline-block">
            &larr; All Projects
          </Link>
          <h2 className="font-heading text-2xl font-bold text-olive">{project.name}</h2>
          {project.client && <p className="text-warm-gray">{project.client}</p>}
          <p className="text-sm text-sage font-heading">#{project.number}</p>
        </div>
        <button
          onClick={fetchProject}
          className="bg-olive text-white font-heading font-bold px-6 py-3 rounded-lg hover:bg-warm-gray transition shadow-md text-lg"
        >
          Refresh from Archicad
        </button>
      </div>

      <div className="bg-white rounded-lg shadow-md p-4 mb-6 flex items-center justify-between text-sm">
        <span className="text-warm-gray">
          Last synced:{' '}
          {project.last_synced
            ? new Date(project.last_synced).toLocaleString()
            : 'Never'}
        </span>
        <span className="text-olive font-bold">
          {Object.values(schedules).reduce((a, b) => a + b, 0)} total items
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {Object.entries(SCHEDULE_LABELS).map(([key, label]) => {
          const count = schedules[key] || 0
          return (
            <div
              key={key}
              className="bg-white rounded-lg shadow p-4 border-t-4 border-olive text-center hover:shadow-md transition"
            >
              <p className="font-heading font-bold text-3xl text-olive mb-1">{count}</p>
              <p className="text-warm-gray text-sm font-heading">{label}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default Dashboard
