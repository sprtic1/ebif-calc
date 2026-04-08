import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import Home from './pages/Home'
import NewProject from './pages/NewProject'
import Dashboard from './pages/Dashboard'

function App() {
  return (
    <BrowserRouter>
      <nav className="bg-olive text-white px-6 py-4 shadow-md">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <Link to="/" className="font-heading font-black text-2xl tracking-tight hover:opacity-90">
            EID Project Hub
          </Link>
          <Link
            to="/new"
            className="bg-white text-olive font-heading font-bold px-4 py-2 rounded hover:bg-light-sage transition"
          >
            + New Project
          </Link>
        </div>
      </nav>
      <main className="max-w-6xl mx-auto px-6 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/new" element={<NewProject />} />
          <Route path="/project/:id" element={<Dashboard />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}

export default App
