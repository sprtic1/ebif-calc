import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'

const SCHEDULE_LABELS = {
  appliances: 'Appliances',
  bath_accessories: 'Bath Accessories',
  cabinetry_hardware: 'Cabinetry Hardware',
  cabinetry_inserts: 'Cabinetry Inserts',
  cabinetry_style: 'Cabinetry Style & Species',
  countertops: 'Countertops',
  decorative_lighting: 'Decorative Lighting',
  door_hardware: 'Door Hardware',
  flooring: 'Flooring',
  furniture: 'Furniture',
  lighting_electrical: 'Lighting & Electrical',
  plumbing: 'Plumbing',
  shower_glass_mirrors: 'Shower Glass & Mirrors',
  specialty_equipment: 'Specialty Equipment',
  surface_finishes: 'Surface Finishes',
  tile: 'Tile',
}

function Dashboard() {
  const { id } = useParams()
  const [project, setProject] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Archicad sync state
  const [syncing, setSyncing] = useState(false)
  const [syncError, setSyncError] = useState('')
  const [preview, setPreview] = useState(null)
  const [writing, setWriting] = useState(false)

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

  const handlePreview = async () => {
    setSyncing(true)
    setSyncError('')
    setPreview(null)
    try {
      const res = await fetch(`/api/projects/${id}/preview`)
      const data = await res.json()
      if (!res.ok) {
        setSyncError(data.error || 'Preview failed')
        setSyncing(false)
        return
      }
      setPreview(data)
      setSyncing(false)
    } catch {
      setSyncError('Cannot connect to Archicad — is it running with Tapir?')
      setSyncing(false)
    }
  }

  const handleConfirmRefresh = async () => {
    setWriting(true)
    setSyncError('')
    try {
      const res = await fetch(`/api/projects/${id}/refresh`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) {
        setSyncError(data.error || 'Refresh failed')
        setWriting(false)
        return
      }
      setProject(data.project)
      setPreview(null)
      setWriting(false)
      if (data.excel_error) {
        setSyncError(`Data synced but Excel write failed: ${data.excel_error}`)
      }
    } catch {
      setSyncError('Cannot connect to Archicad — is it running with Tapir?')
      setWriting(false)
    }
  }

  if (loading) return <p className="text-warm-gray">Loading...</p>
  if (error) return <p className="text-red-600">{error}</p>
  if (!project) return <p className="text-warm-gray">Project not found.</p>

  const schedules = project.schedules || {}
  const totalItems = Object.values(schedules).reduce((a, b) => a + b, 0)

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to="/" className="text-olive hover:underline text-sm font-heading mb-1 inline-block">
            &larr; All Projects
          </Link>
          <h2 className="font-heading text-2xl font-bold text-olive">{project.project_name}</h2>
          {project.client_name && <p className="text-warm-gray">{project.client_name}</p>}
          {project.address && <p className="text-sm text-sage font-heading">{project.address}</p>}
        </div>
        <button
          onClick={handlePreview}
          disabled={syncing || writing}
          className="bg-olive text-white font-heading font-bold px-6 py-3 rounded-lg hover:bg-warm-gray transition shadow-md text-lg disabled:opacity-50"
        >
          {syncing ? 'Connecting...' : 'Refresh from Archicad'}
        </button>
      </div>

      {/* Sync error banner */}
      {syncError && (
        <div className="bg-red-100 border border-red-300 text-red-700 px-4 py-3 rounded mb-4">
          {syncError}
          <button onClick={() => setSyncError('')} className="ml-4 text-red-500 font-bold">&times;</button>
        </div>
      )}

      {/* Preview modal overlay */}
      {preview && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-8 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto">
            <h3 className="font-heading text-xl font-bold text-olive mb-4">
              Archicad Preview — {preview.total} elements found
            </h3>
            <div className="space-y-2 mb-6">
              {Object.entries(SCHEDULE_LABELS).map(([key, label]) => {
                const count = preview.counts?.[key] || 0
                return (
                  <div key={key} className="flex justify-between items-center py-1 border-b border-gray-100">
                    <span className="text-warm-gray font-heading">{label}</span>
                    <span className={`font-heading font-bold ${count > 0 ? 'text-olive' : 'text-gray-300'}`}>
                      {count}
                    </span>
                  </div>
                )
              })}
            </div>
            <p className="text-xs text-warm-gray mb-4">
              This will write Archicad data into the EID Master Schedule. Manual columns will NOT be touched.
            </p>
            <div className="flex gap-3">
              <button
                onClick={handleConfirmRefresh}
                disabled={writing}
                className="flex-1 bg-olive text-white font-heading font-bold py-3 rounded-lg hover:bg-warm-gray transition disabled:opacity-50"
              >
                {writing ? 'Writing to Excel...' : 'Confirm & Write'}
              </button>
              <button
                onClick={() => setPreview(null)}
                disabled={writing}
                className="flex-1 bg-gray-200 text-warm-gray font-heading font-bold py-3 rounded-lg hover:bg-gray-300 transition disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg shadow-md p-4 mb-6 flex items-center justify-between text-sm">
        <span className="text-warm-gray">
          Last synced:{' '}
          {project.last_synced
            ? new Date(project.last_synced).toLocaleString()
            : 'Never'}
        </span>
        <span className="text-olive font-bold">
          {totalItems} total items
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {Object.entries(SCHEDULE_LABELS).map(([key, label]) => {
          const count = schedules[key] || 0
          const populated = count > 0
          return (
            <div
              key={key}
              className={`bg-white rounded-lg shadow p-4 text-center hover:shadow-md transition ${
                populated ? 'border-t-4 border-olive' : 'border-t-4 border-gray-200'
              }`}
            >
              <p className={`font-heading font-bold text-3xl mb-1 ${
                populated ? 'text-olive' : 'text-gray-300'
              }`}>
                {count}
              </p>
              <p className={`text-sm font-heading ${
                populated ? 'text-warm-gray' : 'text-gray-400'
              }`}>
                {label}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default Dashboard
