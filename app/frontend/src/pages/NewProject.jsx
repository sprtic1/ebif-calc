import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

function parseFolderName(folderPath) {
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

export default function NewProject() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    folder_location: '',
    project_name: '',
    client_name: '',
    address: '',
  })
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const handleFolderChange = e => {
    const folder = e.target.value
    const parsed = parseFolderName(folder)
    setForm({
      folder_location: folder,
      project_name: parsed.project_name,
      client_name: parsed.client_name,
      address: parsed.address,
    })
  }

  const handleChange = e => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = async e => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      const res = await fetch('/project-manager/api/projects', {
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
      navigate(`/project/${data.project.id}`)
    } catch (err) {
      setError('Network error — is the backend running?')
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-3xl font-heading font-bold text-eid-dark mb-8">New Project</h1>

      <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow p-8 space-y-6">
        {/* Folder Location — triggers auto-fill */}
        <div>
          <label className="block text-sm font-heading font-bold text-eid-dark mb-1">
            Folder Location
          </label>
          <input
            type="text"
            name="folder_location"
            value={form.folder_location}
            onChange={handleFolderChange}
            placeholder="C:\Users\linco\EID Dropbox\PROJECTS\MCCOLLUM - 408 CAYUSE COURT"
            required
            className="w-full border border-eid-sage rounded-lg px-4 py-2 text-eid-dark focus:outline-none focus:ring-2 focus:ring-eid-olive"
          />
          <p className="text-xs text-eid-warm-gray mt-1">
            Paste the full project folder path — fields below auto-fill from the folder name
          </p>
        </div>

        {/* Project Name */}
        <div>
          <label className="block text-sm font-heading font-bold text-eid-dark mb-1">
            Project Name
          </label>
          <input
            type="text"
            name="project_name"
            value={form.project_name}
            onChange={handleChange}
            placeholder="MCCOLLUM - 408 CAYUSE COURT"
            required
            className="w-full border border-eid-sage rounded-lg px-4 py-2 text-eid-dark focus:outline-none focus:ring-2 focus:ring-eid-olive"
          />
        </div>

        {/* Client Name */}
        <div>
          <label className="block text-sm font-heading font-bold text-eid-dark mb-1">
            Client Name
          </label>
          <input
            type="text"
            name="client_name"
            value={form.client_name}
            onChange={handleChange}
            placeholder="MCCOLLUM"
            required
            className="w-full border border-eid-sage rounded-lg px-4 py-2 text-eid-dark focus:outline-none focus:ring-2 focus:ring-eid-olive"
          />
        </div>

        {/* Address */}
        <div>
          <label className="block text-sm font-heading font-bold text-eid-dark mb-1">
            Address
          </label>
          <input
            type="text"
            name="address"
            value={form.address}
            onChange={handleChange}
            placeholder="408 CAYUSE COURT"
            className="w-full border border-eid-sage rounded-lg px-4 py-2 text-eid-dark focus:outline-none focus:ring-2 focus:ring-eid-olive"
          />
        </div>

        {error && (
          <p className="text-red-600 text-sm">{error}</p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-eid-olive hover:bg-eid-warm-gray text-white font-heading font-bold py-3 rounded-lg transition-colors disabled:opacity-50"
        >
          {submitting ? 'Creating...' : 'Create Project'}
        </button>
      </form>
    </div>
  )
}
