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
  playTone(523, 0.15)
  setTimeout(() => playTone(659, 0.15), 150)
  setTimeout(() => playTone(784, 0.3), 300)
}

function playErrorSound() {
  playTone(330, 0.25, 'square')
  setTimeout(() => playTone(262, 0.4, 'square'), 300)
}

function Dashboard() {
  const { id } = useParams()
  const [project, setProject] = useState(null)
  const [details, setDetails] = useState(null)
  const [summary, setSummary] = useState(null)
  const [pullHistory, setPullHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expandedTile, setExpandedTile] = useState(null)

  // Export state
  const [exporting, setExporting] = useState(false)

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

  // Tear sheet scanner state
  const [scanning, setScanning] = useState(false)
  const [scanProgress, setScanProgress] = useState(null)

  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

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

  const fetchDetails = (silent = false) => {
    if (!silent) setLoading(true)
    fetch(`/api/projects/${id}/details`)
      .then((res) => {
        if (!res.ok) throw new Error('Project not found')
        return res.json()
      })
      .then((data) => {
        setProject(data.project)
        setDetails(data.schedule_details)
        setSummary(data.summary)
        setPullHistory(data.pull_history || [])
        setLoading(false)
      })
      .catch((err) => {
        if (!silent) setError(err.message)
        setLoading(false)
      })
  }

  useEffect(() => {
    fetchDetails()
  }, [id])

  const cancelRetry = () => {
    if (retryTimer) {
      clearTimeout(retryTimer)
      setRetryTimer(null)
    }
    setSyncing(false)
    setSyncStatus('')
  }

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
            if (msg.error) { setSyncError(msg.error); setWriting(false); setWriteProgress(null); playErrorSound(); return }
            if (msg.progress) setWriteProgress(msg.progress)
            if (msg.result) finalResult = msg.result
          } catch { /* skip */ }
        }
      }
      if (finalResult) {
        const total = finalResult.total || 0
        setPreview(null)
        setSelectedPort(null)
        setWriteProgress(null)
        setWriting(false)
        const cloudMsg = finalResult.cloud_sync?.ok ? ' \u2014 Cloud synced' : ''
        setToast(`Success! ${total} items written${cloudMsg}`)
        showBrowserNotification(`Archicad sync complete \u2014 ${total} items updated${cloudMsg}`)
        playSuccessSound()
        fetchDetails(true) // Silent reload — reads fresh counts from Excel
        if (finalResult.excel_error) setSyncError(`Data synced but: ${finalResult.excel_error}`)
        if (finalResult.cloud_sync && !finalResult.cloud_sync.ok && finalResult.cloud_sync.message) {
          setSyncError(prev => prev ? `${prev} | ${finalResult.cloud_sync.message}` : finalResult.cloud_sync.message)
        }
      } else {
        setSyncError('Refresh completed but no result received'); setWriting(false); setWriteProgress(null); playErrorSound()
      }
    } catch {
      setSyncError("Please make sure the Tapir palette is open in your running Archicad session, then hit the 'Refresh from Archicad' button again!")
      setWriting(false); setWriteProgress(null); playErrorSound()
    }
  }, [id])

  const scanForPort = async () => {
    try {
      const res = await fetch(`/api/projects/${id}/find-port`)
      const data = await res.json()

      if (data.matched) {
        // Auto-matched by project name — proceed directly
        setSyncStatus('')
        await fetchPreviewAndRefresh(data.port)
        return
      }

      if (data.instances && data.instances.length > 0) {
        // Multiple instances, no auto-match — show selector
        setSyncStatus('')
        if (data.instances.length === 1) {
          await fetchPreviewAndRefresh(data.instances[0].port)
        } else {
          setInstances(data.instances); setSyncing(false)
        }
        return
      }
    } catch { /* retry */ }

    // No instances found — retry in 5 seconds
    setSyncStatus('Waiting for Tapir...')
    const timer = setTimeout(() => scanForPort(), 5000)
    setRetryTimer(timer)
  }

  const handleRefreshClick = async () => {
    setSyncing(true); setSyncError(''); setSyncStatus('Scanning...')
    setInstances(null); setPreview(null); setSelectedPort(null)
    await scanForPort()
  }

  const handleInstanceSelect = async (port) => {
    setInstances(null); setSyncing(true)
    await fetchPreviewAndRefresh(port)
  }

  const fetchPreviewAndRefresh = async (port) => {
    setSelectedPort(port); setSyncStatus('Loading preview...')
    try {
      const res = await fetch(`/api/projects/${id}/preview?port=${port}`)
      const data = await res.json()
      if (!res.ok) { setSyncError(data.error || 'Preview failed'); setSyncing(false); playErrorSound(); return }
      setSyncError(''); setPreview(data); setSyncing(false)
      await doRefresh(port)
    } catch {
      setSyncError("Please make sure the Tapir palette is open in your running Archicad session, then hit the 'Refresh from Archicad' button again!")
      setSyncing(false); playErrorSound()
    }
  }

  const handleScanTearSheets = async () => {
    setScanning(true); setSyncError('')
    setScanProgress({ phase: 'publishing', step: 0, total: 0, pdf: 'Starting...' })
    try {
      const res = await fetch(`/api/projects/${id}/scan-tearsheets`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ port: project?.last_tapir_port }),
      })
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = '', finalResult = null
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n'); buffer = lines.pop()
        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const msg = JSON.parse(line)
            if (msg.error) { setSyncError(msg.error); setScanning(false); setScanProgress(null); playErrorSound(); return }
            if (msg.progress) setScanProgress(msg.progress)
            if (msg.result) finalResult = msg.result
          } catch { /* skip */ }
        }
      }
      if (finalResult) {
        setScanning(false); setScanProgress(null)
        setToast(`Processed ${finalResult.processed} tear sheets. Updated ${finalResult.updated} rows.`)
        showBrowserNotification(`Tear sheet scan complete`); playSuccessSound(); fetchDetails(true)
        if (finalResult.errors?.length) setSyncError(finalResult.errors.join(' | '))
      } else { setScanning(false); setScanProgress(null); setSyncError('Scan completed but no result received'); playErrorSound() }
    } catch { setSyncError('Tear sheet scan failed'); setScanning(false); setScanProgress(null); playErrorSound() }
  }

  const handleRefreshExcel = async () => {
    setSyncing(true)
    setSyncStatus('Reading Excel...')
    setSyncError('')
    try {
      const res = await fetch(`/api/projects/${id}/refresh-excel`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) {
        setSyncError(data.error || 'Failed to read Excel')
        setSyncing(false)
        playErrorSound()
        return
      }
      setProject(data.project)
      setDetails(data.schedule_details)
      setSummary(data.summary)
      setPullHistory(data.pull_history || [])
      setSyncing(false)
      const cloudMsg = data.cloud_sync?.ok ? ' — Cloud synced' : ''
      setToast(`Excel refreshed! ${data.summary?.total || 0} items${cloudMsg}`)
      playSuccessSound()
      if (data.cloud_sync && !data.cloud_sync.ok && data.cloud_sync.message) {
        setSyncError(data.cloud_sync.message)
      }
    } catch {
      setSyncError('Failed to read Excel file')
      setSyncing(false)
      playErrorSound()
    }
  }

  const handleExportGC = async () => {
    setExporting(true)
    setSyncError('')
    try {
      const res = await fetch(`/api/projects/${id}/export-gc`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) {
        setSyncError(data.error || 'Export failed')
        setExporting(false)
        playErrorSound()
        return
      }
      setExporting(false)
      setToast(`GC Package exported! ${data.tabs} tabs, ${data.rows} rows`)
      playSuccessSound()
    } catch {
      setSyncError('Export failed')
      setExporting(false)
      playErrorSound()
    }
  }

  const handleOpenExcel = async () => {
    try {
      const res = await fetch(`/api/projects/${id}/open-excel`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) setSyncError(data.error || 'Could not open Excel')
    } catch { setSyncError('Could not open Excel file') }
  }

  if (loading) return <p className="text-warm-gray p-8">Loading...</p>
  if (error) return <p className="text-red-600 p-8">{error}</p>
  if (!project) return <p className="text-warm-gray p-8">Project not found.</p>

  const s = summary || { total: 0, complete: 0, incomplete: 0, empty_schedules: 16 }
  const d = details || {}

  return (
    <div>
      {/* Toast */}
      {toast && (
        <div className="fixed top-6 right-6 z-50 bg-olive text-white font-heading font-bold px-6 py-3 rounded-lg shadow-lg">
          {toast}
        </div>
      )}

      {/* ===== 1. HEADER ===== */}
      <div className="mb-6">
        {/* Top row: back arrow */}
        <Link to="/" className="text-olive hover:text-warm-gray transition inline-block mb-1">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </Link>

        {/* Second row: title left, buttons+hint right */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="font-heading text-3xl font-bold text-olive">{project.project_name}</h1>
            <p className="text-xs text-warm-gray mt-1">
              Last synced: {project.last_synced ? new Date(project.last_synced).toLocaleString() : 'Never'}
            </p>
          </div>
          <div className="flex flex-col items-end flex-shrink-0">
            <div className="flex items-center gap-2">
              {syncing && syncStatus && (
                <button onClick={cancelRetry} className="text-warm-gray font-heading font-bold px-4 py-2 rounded-lg hover:text-red-600 transition text-sm">
                  Cancel
                </button>
              )}
              <button onClick={handleRefreshExcel} disabled={syncing || writing}
                className="bg-sage text-olive font-heading font-bold px-4 py-2 rounded-lg hover:bg-olive hover:text-white transition shadow text-sm disabled:opacity-50">
                {syncing && syncStatus === 'Reading Excel...' ? 'Reading...' : 'Refresh from Excel'}
              </button>
              <button onClick={handleRefreshClick} disabled={syncing || writing}
                className="bg-olive text-white font-heading font-bold px-4 py-2 rounded-lg hover:bg-warm-gray transition shadow text-sm disabled:opacity-50">
                {syncing && syncStatus !== 'Reading Excel...' ? (syncStatus || 'Scanning...') : 'Refresh from Archicad'}
              </button>
              <button onClick={handleScanTearSheets} disabled={scanning || syncing || writing}
                className="bg-warm-gray text-white font-heading font-bold px-4 py-2 rounded-lg hover:bg-olive transition shadow text-sm disabled:opacity-50">
                {scanning ? 'Scanning...' : 'Scan Tear Sheets'}
              </button>
              <button type="button" onClick={handleOpenExcel} title="Open in Excel"
                className="bg-white text-olive border border-sage transition cursor-pointer px-3 py-2 rounded-lg hover:bg-light-sage">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="pointer-events-none">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="8" y1="13" x2="16" y2="13" />
                  <line x1="8" y1="17" x2="16" y2="17" />
                </svg>
              </button>
              <button type="button" onClick={handleExportGC} disabled={exporting} title="Export Excel"
                className="bg-white text-olive border border-sage transition cursor-pointer px-3 py-2 rounded-lg hover:bg-light-sage disabled:opacity-50">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="pointer-events-none">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
              </button>
            </div>
            <p className="text-xs text-warm-gray mt-1 text-right w-full">
              Updates the EBIF MASTER TEMPLATE in this project's Dropbox folder, directly from the live Archicad model. The project must be open in Archicad with the Tapir palette running.
            </p>
          </div>
        </div>
      </div>

      {/* Error banner */}
      {syncError && (
        <div className="bg-red-100 border border-red-300 text-red-700 px-4 py-3 rounded mb-4">
          {syncError}
          <button onClick={() => setSyncError('')} className="ml-4 text-red-500 font-bold">&times;</button>
        </div>
      )}

      {/* ===== 2. SUMMARY CARDS ===== */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4 text-center border-t-4 border-olive">
          <p className="font-heading font-bold text-3xl text-olive">{s.total}</p>
          <p className="text-sm font-heading text-warm-gray">Total Items</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4 text-center border-t-4 border-olive">
          <p className="font-heading font-bold text-3xl text-olive">{s.complete}</p>
          <p className="text-sm font-heading text-warm-gray">Complete</p>
        </div>
        <div className={`bg-white rounded-lg shadow p-4 text-center border-t-4 ${s.incomplete > 0 ? 'border-yellow-500' : 'border-olive'}`}>
          <p className={`font-heading font-bold text-3xl ${s.incomplete > 0 ? 'text-yellow-600' : 'text-olive'}`}>{s.incomplete}</p>
          <p className="text-sm font-heading text-warm-gray">Needs Attention</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4 text-center border-t-4 border-gray-200">
          <p className="font-heading font-bold text-3xl text-gray-400">{s.empty_schedules}</p>
          <p className="text-sm font-heading text-warm-gray">Empty Schedules</p>
        </div>
      </div>

      {/* ===== 3. SCHEDULE TILES ===== */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-6">
        {Object.entries(SCHEDULE_LABELS).map(([key, label]) => {
          const sd = d[key] || { count: 0, complete: 0, incomplete: 0, rows: [] }
          const count = sd.count
          // Color: green if all complete, yellow if incomplete, gray if empty
          let borderColor = 'border-gray-200'
          let countColor = 'text-gray-300'
          let labelColor = 'text-gray-400'
          if (count > 0 && sd.incomplete === 0) {
            borderColor = 'border-olive'; countColor = 'text-olive'; labelColor = 'text-warm-gray'
          } else if (count > 0) {
            borderColor = 'border-yellow-500'; countColor = 'text-yellow-600'; labelColor = 'text-warm-gray'
          }
          const isExpanded = expandedTile === key

          return (
            <div key={key}>
              <div
                onClick={() => setExpandedTile(isExpanded ? null : key)}
                className={`bg-white rounded-lg shadow p-4 text-center hover:shadow-md transition cursor-pointer border-t-4 ${borderColor}`}
              >
                <p className={`font-heading font-bold text-3xl mb-1 ${countColor}`}>{count}</p>
                <p className={`text-sm font-heading ${labelColor}`}>{label}</p>
                {count > 0 && sd.incomplete > 0 && (
                  <p className="text-xs text-yellow-600 mt-1">{sd.incomplete} incomplete</p>
                )}
              </div>
              {/* Expanded row detail */}
              {isExpanded && sd.rows.length > 0 && (
                <div className="bg-white rounded-b-lg shadow-inner border-x border-b border-gray-200 p-3 -mt-1">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-warm-gray font-heading">
                        <th className="text-left pb-1">TS#</th>
                        <th className="text-left pb-1">Location</th>
                        <th className="text-left pb-1">Manufacturer</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sd.rows.slice(0, 20).map((row, i) => (
                        <tr key={i} className={i % 2 === 0 ? 'bg-light-sage' : ''}>
                          <td className="py-0.5 pr-2 font-mono">{row.tear_sheet || '\u2014'}</td>
                          <td className="py-0.5 pr-2">{row.location || '\u2014'}</td>
                          <td className={`py-0.5 ${row.manufacturer ? 'text-olive font-bold' : 'text-gray-300 italic'}`}>
                            {row.manufacturer || 'empty'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {sd.rows.length > 20 && (
                    <p className="text-xs text-warm-gray mt-1 text-center">+ {sd.rows.length - 20} more rows</p>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* ===== 4. PULL HISTORY ===== */}
      {pullHistory.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-heading font-bold text-olive mb-3">Pull History</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-warm-gray font-heading border-b border-gray-200">
                <th className="text-left pb-2">Date</th>
                <th className="text-right pb-2">Items</th>
              </tr>
            </thead>
            <tbody>
              {[...pullHistory].reverse().map((entry, i) => (
                <tr key={i} className={i % 2 === 0 ? 'bg-light-sage' : ''}>
                  <td className="py-1.5">{new Date(entry.timestamp).toLocaleString()}</td>
                  <td className="py-1.5 text-right font-heading font-bold text-olive">{entry.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ===== MODALS (preserved from existing) ===== */}

      {/* Instance selector */}
      {instances && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-8 max-w-md w-full mx-4">
            <h3 className="font-heading text-xl font-bold text-olive mb-2">Multiple Archicad Instances Found</h3>
            <p className="text-sm text-warm-gray mb-6">Select which project to pull data from:</p>
            <div className="space-y-3 mb-6">
              {instances.map((inst) => (
                <button key={inst.port} onClick={() => handleInstanceSelect(inst.port)}
                  className="w-full text-left bg-light-sage hover:bg-sage rounded-lg p-4 transition border border-sage">
                  <p className="font-heading font-bold text-olive">{inst.project_name}</p>
                  <p className="text-xs text-warm-gray mt-1">Port {inst.port} &middot; Archicad {inst.version}</p>
                </button>
              ))}
            </div>
            <button onClick={() => setInstances(null)}
              className="w-full bg-gray-200 text-warm-gray font-heading font-bold py-3 rounded-lg hover:bg-gray-300 transition">Cancel</button>
          </div>
        </div>
      )}

      {/* Archicad sync progress */}
      {preview && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-8 max-w-2xl w-full mx-4">
            <h3 className="font-heading text-xl font-bold text-olive mb-4">Archicad Sync — {preview.total} elements</h3>
            <div className="grid grid-cols-2 gap-x-8 gap-y-1 mb-6">
              {Object.entries(SCHEDULE_LABELS).map(([key, label]) => {
                const count = preview.counts?.[key] || 0
                return (
                  <div key={key} className="flex justify-between items-center py-1 border-b border-gray-100">
                    <span className="text-warm-gray font-heading text-sm">{label}</span>
                    <span className={`font-heading font-bold text-sm ${count > 0 ? 'text-olive' : 'text-gray-300'}`}>{count}</span>
                  </div>
                )
              })}
            </div>
            {writing && writeProgress && (() => {
              const phase = writeProgress.phase === 'extracting' ? 'Extracting' : 'Writing'
              const hasItems = writeProgress.items_total != null && writeProgress.items_total > 0
              const barPct = hasItems ? Math.round((writeProgress.items_so_far / writeProgress.items_total) * 100) : Math.round((writeProgress.step / writeProgress.total) * 100)
              return (
                <div className="mb-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-heading text-olive">{phase} {writeProgress.category}...</span>
                    <span className="text-sm font-heading text-warm-gray">
                      {hasItems ? `${writeProgress.items_so_far}/${writeProgress.items_total} items (${barPct}%)` : `${writeProgress.step}/${writeProgress.total} (${barPct}%)`}
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div className="bg-olive h-3 rounded-full transition-all duration-300" style={{ width: `${barPct}%` }} />
                  </div>
                </div>
              )
            })()}
            {writing && !writeProgress && <p className="text-sm font-heading text-olive mb-4">Connecting to Archicad...</p>}
            <p className="text-xs text-warm-gray">Writing Archicad data. Manual columns will NOT be touched.</p>
          </div>
        </div>
      )}

      {/* Tear sheet scan progress */}
      {scanning && scanProgress && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-8 max-w-md w-full mx-4">
            <h3 className="font-heading text-xl font-bold text-olive mb-4">
              {scanProgress.phase === 'publishing' ? 'Publishing Tear Sheets' : 'Scanning Tear Sheets'}
            </h3>
            {scanProgress.phase === 'publishing' && <p className="text-sm text-warm-gray mb-4">Exporting PDFs from Archicad...</p>}
            {scanProgress.phase === 'scanning' && scanProgress.total > 0 && (
              <div className="mb-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-heading text-olive truncate mr-2">{scanProgress.pdf}</span>
                  <span className="text-sm font-heading text-warm-gray whitespace-nowrap">
                    {scanProgress.step}/{scanProgress.total} ({Math.round((scanProgress.step / scanProgress.total) * 100)}%)
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div className="bg-olive h-3 rounded-full transition-all duration-300" style={{ width: `${(scanProgress.step / scanProgress.total) * 100}%` }} />
                </div>
              </div>
            )}
            <p className="text-xs text-warm-gray">Detecting colored highlights and extracting text via OCR...</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default Dashboard
