import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

export default function Home() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/projects')
      .then(r => r.json())
      .then(data => { setProjects(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-heading font-bold text-eid-dark">Projects</h1>
        <Link
          to="/new"
          className="bg-eid-olive hover:bg-eid-warm-gray text-white font-heading font-bold px-6 py-3 rounded-lg transition-colors"
        >
          + New Project
        </Link>
      </div>

      {loading ? (
        <p className="text-eid-warm-gray">Loading projects...</p>
      ) : projects.length === 0 ? (
        <div className="bg-white rounded-xl shadow p-12 text-center">
          <p className="text-eid-warm-gray text-lg mb-4">No projects yet</p>
          <Link
            to="/new"
            className="text-eid-olive font-bold underline hover:text-eid-warm-gray"
          >
            Create your first project
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map(p => (
            <Link
              key={p.id}
              to={`/project/${p.id}`}
              className="bg-white rounded-xl shadow hover:shadow-lg transition-shadow p-6 border-l-4 border-eid-olive"
            >
              <h2 className="text-xl font-heading font-bold text-eid-dark mb-1">
                {p.project_name}
              </h2>
              <p className="text-eid-warm-gray text-sm mb-2">{p.client_name}</p>
              <span className="inline-block bg-eid-light-sage text-eid-olive text-xs font-bold px-2 py-1 rounded">
                {p.project_number}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
