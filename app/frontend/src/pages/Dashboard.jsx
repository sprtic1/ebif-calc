import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'

const CATEGORIES = [
  'Walls', 'Floors', 'Roofs', 'Columns',
  'Beams', 'Slabs', 'Stairs', 'Doors',
  'Windows', 'Curtain Walls', 'Railings', 'Zones',
  'Meshes', 'Shells', 'Morphs', 'Objects',
]

export default function Dashboard() {
  const { id } = useParams()
  const [project, setProject] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`/api/projects/${id}`)
      .then(r => r.json())
      .then(data => { setProject(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [id])

  if (loading) return <p className="text-eid-warm-gray">Loading...</p>
  if (!project) return <p className="text-red-600">Project not found</p>

  const catKey = name => name.toLowerCase().replace(' ', '_')

  return (
    <div>
      <Link to="/" className="text-eid-olive hover:underline text-sm mb-4 inline-block">
        &larr; All Projects
      </Link>

      {/* Header */}
      <div className="bg-white rounded-xl shadow p-6 mb-8">
        <h1 className="text-3xl font-heading font-bold text-eid-dark">
          {project.project_name}
        </h1>
        <p className="text-eid-warm-gray mt-1">
          {project.client_name} &middot; {project.project_number}
        </p>
        <p className="text-xs text-eid-sage mt-2">
          Last synced: {project.last_synced || 'Never'}
        </p>
      </div>

      {/* Sync banner */}
      <div className="bg-eid-sage/30 border border-eid-sage rounded-xl p-6 mb-8 text-center">
        <p className="text-eid-warm-gray mb-4">
          No data yet — click Refresh to pull from Archicad
        </p>
        <button
          disabled
          className="bg-eid-olive text-white font-heading font-bold px-8 py-3 rounded-lg opacity-50 cursor-not-allowed"
          title="Available in Phase 2"
        >
          Refresh from Archicad
        </button>
      </div>

      {/* Category tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {CATEGORIES.map(cat => {
          const count = project.categories?.[catKey(cat)] ?? 0
          return (
            <div
              key={cat}
              className="bg-white rounded-xl shadow p-4 text-center border-t-4 border-eid-sage"
            >
              <p className="text-2xl font-heading font-bold text-eid-dark">{count}</p>
              <p className="text-sm text-eid-warm-gray mt-1">{cat}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
