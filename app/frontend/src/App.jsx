import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import NewProject from './pages/NewProject'
import Dashboard from './pages/Dashboard'

export default function App() {
  return (
    <div className="min-h-screen bg-eid-light-sage">
      <header className="bg-eid-olive text-white px-6 py-4 shadow-md">
        <a href="/" className="text-2xl font-heading font-bold tracking-wide">
          EID Project Manager
        </a>
      </header>
      <main className="max-w-6xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/new" element={<NewProject />} />
          <Route path="/project/:id" element={<Dashboard />} />
        </Routes>
      </main>
    </div>
  )
}
