import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function NewProject() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    project_name: '',
    client_name: '',
    project_number: '',
    dropbox_folder: '',
  })
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const handleChange = e => {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  const handleSubmit = async e => {
    e.preventDefault()
    setError(null)
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
      navigate(`/project/${data.project.id}`)
    } catch (err) {
      setError('Network error — is the backend running?')
      setSubmitting(false)
    }
  }

  const fields = [
    { name: 'project_name', label: 'Project Name', placeholder: 'Ellis Beach Chalet 29' },
    { name: 'client_name', label: 'Client Name', placeholder: 'EID Architecture' },
    { name: 'project_number', label: 'Project Number', placeholder: '2024-031' },
    { name: 'dropbox_folder', label: 'Dropbox Folder Path', placeholder: 'C:\\Users\\linco\\EID Dropbox\\PROJECTS\\...' },
  ]

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-3xl font-heading font-bold text-eid-dark mb-8">New Project</h1>

      <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow p-8 space-y-6">
        {fields.map(f => (
          <div key={f.name}>
            <label className="block text-sm font-heading font-bold text-eid-dark mb-1">
              {f.label}
            </label>
            <input
              type="text"
              name={f.name}
              value={form[f.name]}
              onChange={handleChange}
              placeholder={f.placeholder}
              required
              className="w-full border border-eid-sage rounded-lg px-4 py-2 text-eid-dark focus:outline-none focus:ring-2 focus:ring-eid-olive"
            />
          </div>
        ))}

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
