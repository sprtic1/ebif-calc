import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

function NewProject() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    name: '',
    client: '',
    number: '',
    dropbox_path: '',
  })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

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
        <div>
          <label className="block font-heading font-bold text-olive mb-1">Project Name *</label>
          <input
            name="name"
            value={form.name}
            onChange={handleChange}
            required
            className="w-full border border-sage rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-olive"
            placeholder="e.g. McCollum - 408 Cayuse Court"
          />
        </div>
        <div>
          <label className="block font-heading font-bold text-olive mb-1">Client Name</label>
          <input
            name="client"
            value={form.client}
            onChange={handleChange}
            className="w-full border border-sage rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-olive"
            placeholder="e.g. McCollum"
          />
        </div>
        <div>
          <label className="block font-heading font-bold text-olive mb-1">Project Number *</label>
          <input
            name="number"
            value={form.number}
            onChange={handleChange}
            required
            className="w-full border border-sage rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-olive"
            placeholder="e.g. 2024-031"
          />
        </div>
        <div>
          <label className="block font-heading font-bold text-olive mb-1">Dropbox Folder Path</label>
          <input
            name="dropbox_path"
            value={form.dropbox_path}
            onChange={handleChange}
            className="w-full border border-sage rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-olive font-mono text-sm"
            placeholder="C:\Users\linco\EID Dropbox\PROJECTS\..."
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
