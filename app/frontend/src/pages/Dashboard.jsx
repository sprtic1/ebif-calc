import { useEffect, useRef, useState, useCallback } from 'react'
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

// --- Notification sounds via Web Audio API ---
function playTone(frequency, duration, type = 'sine') {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = type
    osc.frequency.value = frequency
    gain.gain.value = 0.15
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + duration)
  } catch { /* audio not available */ }
}

function playSuccessSound() {
  playTone(523, 0.15)  // C5
  setTimeout(() => playTone(659, 0.15), 150) // E5
  setTimeout(() => playTone(784, 0.3), 300)  // G5
}

function playErrorSound() {
  playTone(330, 0.25, 'square') // E4 buzzy
  setTimeout(() => playTone(262, 0.4, 'square'), 300) // C4 buzzy
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
  const [writeProgress, setWriteProgress] = useState(null)
  const [retryTimer, setRetryTimer] = useState(null)
  const [toast, setToast] = useState(null)
  const [btnWidth, setBtnWidth] = useState(0)
  const btnRef = useRef(null)

  useEffect(() => {
    if (btnRef.current) setBtnWidth(btnRef.current.offsetWidth)
  })

  // Request notification permission on mount
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  // Auto-dismiss toast after 4 seconds
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 4000)
      return () => clearTimeout(t)
    }
  }, [toast])

  const showBrowserNotification = (message) => {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('EID Project Manager', { body: message })
    }
  }

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

  // Auto-start refresh when preview loads
  const doRefresh = useCallback(async (port) => {
    setWriting(true)
    setSyncError('')
    setWriteProgress(null)
    try {
      const res = await fetch(`/api/projects/${id}/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ port }),
      })

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let finalResult = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()
        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const msg = JSON.parse(line)
            if (msg.error) {
              setSyncError(msg.error)
              setWriting(false)
              setWriteProgress(null)
              playErrorSound()
              return
            }
            if (msg.progress) {
              setWriteProgress(msg.progress)
            }
            if (msg.result) {
              finalResult = msg.result
            }
          } catch {
            // skip malformed lines
          }
        }
      }

      if (finalResult) {
        const total = finalResult.total || 0
        setProject(finalResult.project)
        setPreview(null)
        setSelectedPort(null)
        setWriteProgress(null)
        setWriting(false)
        setToast(`Success! ${total} items written`)
        showBrowserNotification(`Archicad sync complete \u2014 ${total} items updated`)
        playSuccessSound()
        if (finalResult.excel_error) {
          setSyncError(`Data synced but: ${finalResult.excel_error}`)
        }
      } else {
        setSyncError('Refresh completed but no result received')
        setWriting(false)
        setWriteProgress(null)
        playErrorSound()
      }
    } catch {
      setSyncError("Please make sure the Tapir palette is open in your running Archicad session, then hit the 'Refresh from Archicad' button again!")
      setWriting(false)
      setWriteProgress(null)
      playErrorSound()
    }
  }, [id])

  const scanForInstances = async (preferredPort) => {
    try {
      const res = await fetch('/api/archicad/instances')
      const data = await res.json()

      if (data.instances && data.instances.length > 0) {
        setSyncStatus('')
        if (data.instances.length === 1) {
          await fetchPreviewAndRefresh(data.instances[0].port)
        } else {
          // If preferred port is in the list and only wanting quick reconnect
          if (preferredPort) {
            const preferred = data.instances.find(i => i.port === preferredPort)
            if (preferred) {
              await fetchPreviewAndRefresh(preferred.port)
              return
            }
          }
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
    const timer = setTimeout(() => scanForInstances(null), 5000)
    setRetryTimer(timer)
  }

  const handleRefreshClick = async () => {
    setSyncing(true)
    setSyncError('')
    setSyncStatus('Scanning...')
    setInstances(null)
    setPreview(null)
    setSelectedPort(null)
    const preferredPort = project?.last_tapir_port || null
    await scanForInstances(preferredPort)
  }

  const handleInstanceSelect = async (port) => {
    setInstances(null)
    setSyncing(true)
    await fetchPreviewAndRefresh(port)
  }

  const fetchPreviewAndRefresh = async (port) => {
    setSelectedPort(port)
    setSyncStatus('Loading preview...')
    try {
      const res = await fetch(`/api/projects/${id}/preview?port=${port}`)
      const data = await res.json()
      if (!res.ok) {
        setSyncError(data.error || 'Preview failed')
        setSyncing(false)
        playErrorSound()
        return
      }
      setSyncError('')
      setPreview(data)
      setSyncing(false)
      // Auto-start the refresh immediately
      await doRefresh(port)
    } catch {
      setSyncError("Please make sure the Tapir palette is open in your running Archicad session, then hit the 'Refresh from Archicad' button again!")
      setSyncing(false)
      playErrorSound()
    }
  }

  const handleOpenExcel = async () => {
    try {
      const res = await fetch(`/api/projects/${id}/open-excel`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) {
        setSyncError(data.error || 'Could not open Excel')
      }
    } catch {
      setSyncError('Could not open Excel file')
    }
  }

  if (loading) return <p className="text-warm-gray">Loading...</p>
  if (error) return <p className="text-red-600">{error}</p>
  if (!project) return <p className="text-warm-gray">Project not found.</p>

  const schedules = project.schedules || {}
  const totalItems = Object.values(schedules).reduce((a, b) => a + b, 0)

  return (
    <div>
      {/* Success toast */}
      {toast && (
        <div className="fixed top-6 right-6 z-50 bg-olive text-white font-heading font-bold px-6 py-3 rounded-lg shadow-lg animate-fade-in">
          {toast}
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to="/" className="text-olive hover:underline text-sm font-heading mb-1 inline-block">
            &larr; All Projects
          </Link>
          <h2 className="font-heading text-2xl font-bold text-olive">{project.project_name}</h2>
          {project.client_name && <p className="text-warm-gray">{project.client_name}</p>}
          {project.address && <p className="text-sm text-sage font-heading">{project.address}</p>}
        </div>
        <div className="flex flex-col items-end">
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
              ref={btnRef}
              onClick={handleRefreshClick}
              disabled={syncing || writing}
              className="bg-olive text-white font-heading font-bold px-6 py-3 rounded-lg hover:bg-warm-gray transition shadow-md text-lg disabled:opacity-50"
            >
              {syncing ? (syncStatus || 'Scanning...') : 'Refresh from Archicad'}
            </button>
          </div>
          <p
            className="text-xs text-warm-gray mt-2 text-center"
            style={btnWidth ? { maxWidth: btnWidth } : undefined}
          >
            Updates the EBIF MASTER TEMPLATE in this project's Dropbox folder, directly from the live Archicad model. The project must be open in Archicad with the Tapir palette running.
          </p>
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

      {/* Progress modal — shows preview counts + live progress */}
      {preview && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-8 max-w-2xl w-full mx-4">
            <h3 className="font-heading text-xl font-bold text-olive mb-4">
              Archicad Sync — {preview.total} elements
            </h3>
            <div className="grid grid-cols-2 gap-x-8 gap-y-1 mb-6">
              {Object.entries(SCHEDULE_LABELS).map(([key, label]) => {
                const count = preview.counts?.[key] || 0
                return (
                  <div key={key} className="flex justify-between items-center py-1 border-b border-gray-100">
                    <span className="text-warm-gray font-heading text-sm">{label}</span>
                    <span className={`font-heading font-bold text-sm ${count > 0 ? 'text-olive' : 'text-gray-300'}`}>
                      {count}
                    </span>
                  </div>
                )
              })}
            </div>

            {/* Progress bar */}
            {writing && writeProgress && (() => {
              const phase = writeProgress.phase === 'extracting' ? 'Extracting' : 'Writing'
              const hasItems = writeProgress.items_total != null && writeProgress.items_total > 0
              const barPct = hasItems
                ? Math.round((writeProgress.items_so_far / writeProgress.items_total) * 100)
                : Math.round((writeProgress.step / writeProgress.total) * 100)
              return (
                <div className="mb-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-heading text-olive">
                      {phase} {writeProgress.category}...
                    </span>
                    <span className="text-sm font-heading text-warm-gray">
                      {hasItems
                        ? `${writeProgress.items_so_far}/${writeProgress.items_total} items (${barPct}%)`
                        : writeProgress.items_so_far > 0
                          ? `${writeProgress.items_so_far} items (${barPct}%)`
                          : `${writeProgress.step}/${writeProgress.total} (${barPct}%)`
                      }
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div
                      className="bg-olive h-3 rounded-full transition-all duration-300"
                      style={{ width: `${barPct}%` }}
                    />
                  </div>
                </div>
              )
            })()}

            {writing && !writeProgress && (
              <div className="mb-4">
                <p className="text-sm font-heading text-olive">Connecting to Archicad...</p>
              </div>
            )}

            <p className="text-xs text-warm-gray">
              Writing Archicad data into the EBIF Master Template. Manual columns will NOT be touched.
            </p>
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
        <div className="flex items-center gap-4">
          <span className="text-olive font-bold">
            {totalItems} total items
          </span>
          <button
            type="button"
            onClick={handleOpenExcel}
            className="text-olive hover:text-warm-gray transition cursor-pointer p-1 rounded hover:bg-gray-100"
            title="Open in Excel"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="pointer-events-none">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="8" y1="13" x2="16" y2="13" />
              <line x1="8" y1="17" x2="16" y2="17" />
              <line x1="10" y1="9" x2="8" y2="9" />
            </svg>
          </button>
        </div>
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
