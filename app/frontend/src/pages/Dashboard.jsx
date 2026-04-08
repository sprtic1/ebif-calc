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
  const [syncStatus, setSyncStatus] = useState('')
  const [syncError, setSyncError] = useState('')
  const [instances, setInstances] = useState(null)
  const [selectedPort, setSelectedPort] = useState(null)
  const [preview, setPreview] = useState(null)
  const [writing, setWriting] = useState(false)
  const [retryTimer, setRetryTimer] = useState(null)

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

  const cancelRetry = () => {
    if (retryTimer) {
      clearTimeout(retryTimer)
      setRetryTimer(null)
    }
    setSyncing(false)
    setSyncStatus('')
  }

  const scanForInstances = async () => {
    try {
      const res = await fetch('/api/archicad/instances')
      const data = await res.json()

      if (data.instances && data.instances.length > 0) {
        // Found instances — stop retrying
        setSyncStatus('')
        if (data.instances.length === 1) {
          await fetchPreview(data.instances[0].port)
        } else {
          setInstances(data.instances)
          setSyncing(false)
        }
        return
      }
    } catch {
      // Network error — keep retrying
    }

    // No instances found — retry in 5 seconds
    setSyncStatus('Waiting for Tapir...')
    const timer = setTimeout(() => scanForInstances(), 5000)
    setRetryTimer(timer)
  }

  const handleRefreshClick = async () => {
    setSyncing(true)
    setSyncError('')
    setSyncStatus('Scanning...')
    setInstances(null)
    setPreview(null)
    setSelectedPort(null)
    await scanForInstances()
  }

  const handleInstanceSelect = async (port) => {
    setInstances(null)
    setSyncing(true)
    await fetchPreview(port)
  }

  const fetchPreview = async (port) => {
    setSelectedPort(port)
    try {
      const res = await fetch(`/api/projects/${id}/preview?port=${port}`)
      const data = await res.json()
      if (!res.ok) {
        setSyncError(data.error || 'Preview failed')
        setSyncing(false)
        return
      }
      setPreview(data)
      setSyncing(false)
    } catch {
      setSyncError("Please make sure the Tapir palette is open in your running Archicad session, then hit the 'Refresh from Archicad' button again!")
      setSyncing(false)
    }
  }

  const handleConfirmRefresh = async () => {
    setWriting(true)
    setSyncError('')
    try {
      const res = await fetch(`/api/projects/${id}/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ port: selectedPort }),
      })
      const data = await res.json()
      if (!res.ok) {
        setSyncError(data.error || 'Refresh failed')
        setWriting(false)
        return
      }
      setProject(data.project)
      setPreview(null)
      setSelectedPort(null)
      setWriting(false)
      if (data.excel_error) {
        setSyncError(`Data synced but Excel write failed: ${data.excel_error}`)
      }
    } catch {
      setSyncError("Please make sure the Tapir palette is open in your running Archicad session, then hit the 'Refresh from Archicad' button again!")
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
        <div className="flex items-center gap-3">
          {syncing && syncStatus && (
            <button
              onClick={cancelRetry}
              className="text-warm-gray font-heading font-bold px-4 py-3 rounded-lg hover:text-red-600 transition text-sm"
            >
              Cancel
            </button>
          )}
          <button
            onClick={handleRefreshClick}
            disabled={syncing || writing}
            className="bg-olive text-white font-heading font-bold px-6 py-3 rounded-lg hover:bg-warm-gray transition shadow-md text-lg disabled:opacity-50"
          >
            {syncing ? (syncStatus || 'Scanning...') : 'Refresh from Archicad'}
          </button>
        </div>
      </div>

      {/* Sync error banner */}
      {syncError && (
        <div className="bg-red-100 border border-red-300 text-red-700 px-4 py-3 rounded mb-4">
          {syncError}
          <button onClick={() => setSyncError('')} className="ml-4 text-red-500 font-bold">&times;</button>
        </div>
      )}

      {/* Instance selector modal */}
      {instances && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-8 max-w-md w-full mx-4">
            <h3 className="font-heading text-xl font-bold text-olive mb-2">
              Multiple Archicad Instances Found
            </h3>
            <p className="text-sm text-warm-gray mb-6">
              Select which project to pull data from:
            </p>
            <div className="space-y-3 mb-6">
              {instances.map((inst) => (
                <button
                  key={inst.port}
                  onClick={() => handleInstanceSelect(inst.port)}
                  className="w-full text-left bg-light-sage hover:bg-sage rounded-lg p-4 transition border border-sage"
                >
                  <p className="font-heading font-bold text-olive">{inst.project_name}</p>
                  <p className="text-xs text-warm-gray mt-1">
                    Port {inst.port} &middot; Archicad {inst.version}
                  </p>
                </button>
              ))}
            </div>
            <button
              onClick={() => setInstances(null)}
              className="w-full bg-gray-200 text-warm-gray font-heading font-bold py-3 rounded-lg hover:bg-gray-300 transition"
            >
              Cancel
            </button>
          </div>
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
                onClick={() => { setPreview(null); setSelectedPort(null) }}
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
