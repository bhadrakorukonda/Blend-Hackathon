import { HashRouter, Routes, Route, Navigate, NavLink, useLocation } from 'react-router-dom'
import MatchDashboard from './pages/MatchDashboard'
import AdminCenter from './pages/AdminCenter'

function NavBar() {
  return (
    <header className="border-b border-[#12123a] bg-[#07071a] sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center gap-6">
        <div className="flex items-center gap-3">
          <span className="text-xl">🩸</span>
          <span className="font-bold text-[#e0e0f4] tracking-widest text-sm">BLOOD WARRIORS</span>
          <span className="text-[#2a2a60] text-[10px] tracking-widest font-mono hidden sm:block">/ COMMAND</span>
        </div>

        <div className="flex-1" />

        <nav className="flex items-center gap-1">
          <NavLink
            to="/coordinator"
            className={({ isActive }) =>
              isActive
                ? 'nav-active-link text-[11px] tracking-widest font-mono'
                : 'text-[11px] tracking-widest font-mono px-4 py-1.5 text-[#5050a0] hover:text-[#9090c0] transition-colors duration-150 rounded'
            }
          >
            COORDINATOR
          </NavLink>
          <NavLink
            to="/admin"
            className={({ isActive }) =>
              isActive
                ? 'nav-active-link text-[11px] tracking-widest font-mono'
                : 'text-[11px] tracking-widest font-mono px-4 py-1.5 text-[#5050a0] hover:text-[#9090c0] transition-colors duration-150 rounded'
            }
          >
            ADMIN
          </NavLink>
        </nav>
      </div>
    </header>
  )
}

function AnimatedRoutes() {
  const location = useLocation()
  return (
    <div key={location.pathname} className="page-enter">
      <Routes location={location}>
        <Route path="/" element={<Navigate to="/coordinator" replace />} />
        <Route path="/coordinator" element={<MatchDashboard />} />
        <Route path="/admin" element={<AdminCenter />} />
      </Routes>
    </div>
  )
}

export default function App() {
  return (
    <HashRouter>
      <div className="min-h-screen bg-[#06060f]">
        <NavBar />
        <AnimatedRoutes />
      </div>
    </HashRouter>
  )
}
