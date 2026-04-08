import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

function Home() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/projects')
      .then((res) => res.json())
      .then((data) => {
        setProjects(data)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  if (loading) {
    return <p className="text-warm-gray">Loading projects...</p>
  }

  if (projects.length === 0) {
    return (
      <div className="text-center py-20">
        <h2 className="font-heading text-3xl font-bold text-olive mb-4">No Projects Yet</h2>
        <p className="text-warm-gray mb-8">Create your first project to get started.</p>
        <Link
          to="/new"
          className="bg-olive text-white font-heading font-bold px-6 py-3 rounded hover:bg-warm-gray transition"
        >
          + New Project
        </Link>
      </div>
    )
  }

  return (
    <div>
      <h2 className="font-heading text-2xl font-bold text-olive mb-6">Projects</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {projects.map((project) => (
          <Link
            key={project.id}
            to={`/project/${project.id}`}
            className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition border-l-4 border-olive"
          >
            <h3 className="font-heading font-bold text-lg text-olive mb-1">{project.name}</h3>
            {project.client && (
              <p className="text-warm-gray text-sm mb-2">{project.client}</p>
            )}
            <p className="text-sm text-sage font-heading">#{project.number}</p>
            <div className="mt-4 flex items-center justify-between text-xs text-warm-gray">
              <span>
                {project.last_synced
                  ? `Synced ${new Date(project.last_synced).toLocaleDateString()}`
                  : 'Never synced'}
              </span>
              <span className="text-olive font-bold">
                {Object.values(project.schedules || {}).reduce((a, b) => a + b, 0)} items
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}

export default Home
