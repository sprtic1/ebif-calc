import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

function parseFolderPath(folderPath) {
  if (!folderPath) return { project_name: '', client_name: '', address: '' }
  // Get the last folder name from the path
  const normalized = folderPath.replace(/\\/g, '/').replace(/\/+$/, '')
  const folderName = normalized.split('/').pop() || ''
  const parts = folderName.split(' - ')
  return {
    project_name: folderName,
    client_name: parts[0]?.trim() || '',
    address: parts.length > 1 ? parts.slice(1).join(' - ').trim() : '',
  }
}

function NewProject() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    folder_location: '',
    project_name: '',
    client_name: '',
    address: '',
  })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [browsing, setBrowsing] = useState(false)

  const applyFolder = (folder) => {
    const parsed = parseFolderPath(folder)
    setForm({
      folder_location: folder,
      project_name: parsed.project_name,
      client_name: parsed.client_name,
      address: parsed.address,
    })
  }

  const handleFolderChange = (e) => {
    applyFolder(e.target.value)
  }

  const handleBrowse = async () => {
    setBrowsing(true)
    try {
      const res = await fetch('/api/browse-folder')
      const data = await res.json()
      if (data.path && !data.cancelled) {
        applyFolder(data.path)
      }
    } catch {
      setError('Could not open folder picker — is the backend running?')
    } finally {
      setBrowsing(false)
    }
  }

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)

    try {
      const res = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.error || 'Failed to create project')
        setSubmitting(false)
        return
      }
      navigate(`/project/${data.id}`)
    } catch {
      setError('Could not connect to server')
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto">
      <h2 className="font-heading text-2xl font-bold text-olive mb-6">New Project</h2>
      {error && (
        <div className="bg-red-100 border border-red-300 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}
      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-md p-8 space-y-5">
        {/* Folder Location — triggers auto-fill */}
        <div>
          <label className="block font-heading font-bold text-olive mb-1">Folder Location *</label>
          <div className="flex gap-2">
            <input
              name="folder_location"
              value={form.folder_location}
              onChange={handleFolderChange}
              required
              className="flex-1 border border-sage rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-olive font-mono text-sm"
              placeholder="C:\Users\linco\EID Dropbox\PROJECTS\MCCOLLUM - 408 CAYUSE COURT"
            />
            <button
              type="button"
              onClick={handleBrowse}
              disabled={browsing}
              className="bg-olive text-white font-heading font-bold px-4 py-2 rounded hover:bg-warm-gray transition disabled:opacity-50 whitespace-nowrap"
            >
              {browsing ? 'Opening...' : 'Browse'}
            </button>
          </div>
          <p className="text-xs text-warm-gray mt-1">
            Browse or paste the full project folder path — fields below auto-fill from the folder name
          </p>
        </div>

        {/* Project Name — auto-filled from folder name */}
        <div>
          <label className="block font-heading font-bold text-olive mb-1">Project Name *</label>
          <input
            name="project_name"
            value={form.project_name}
            onChange={handleChange}
            required
            className="w-full border border-sage rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-olive"
            placeholder="MCCOLLUM - 408 CAYUSE COURT"
          />
        </div>

        {/* Client Name — auto-filled from part before " - " */}
        <div>
          <label className="block font-heading font-bold text-olive mb-1">Client Name *</label>
          <input
            name="client_name"
            value={form.client_name}
            onChange={handleChange}
            required
            className="w-full border border-sage rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-olive"
            placeholder="MCCOLLUM"
          />
        </div>

        {/* Address — auto-filled from part after " - " */}
        <div>
          <label className="block font-heading font-bold text-olive mb-1">Address</label>
          <input
            name="address"
            value={form.address}
            onChange={handleChange}
            className="w-full border border-sage rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-olive"
            placeholder="408 CAYUSE COURT"
          />
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-olive text-white font-heading font-bold py-3 rounded hover:bg-warm-gray transition disabled:opacity-50"
        >
          {submitting ? 'Creating...' : 'Create Project'}
        </button>
      </form>
    </div>
  )
}

export default NewProject
