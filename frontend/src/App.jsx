import { useState, useEffect } from 'react'
import { HashRouter, Routes, Route, Navigate, NavLink, useLocation } from 'react-router-dom'
import MatchDashboard from './pages/MatchDashboard'
import AdminCenter from './pages/AdminCenter'
import PatientPortal from './pages/PatientPortal'

const THEME_KEY = 'blood-warriors-theme'

function ThemeToggle({ theme, onToggle }) {
  const isLight = theme === 'light'
  return (
    <button
      onClick={onToggle}
      aria-label="Toggle light/dark theme"
      className="flex items-center justify-center w-8 h-8 rounded-full border border-[#1c1c3a] text-[#5050a0] hover:text-[#9090c0] hover:border-[#2c2c50] transition-all"
    >
      {isLight ? (
        // Moon icon (click to go dark)
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      ) : (
        // Sun icon (click to go light)
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="5" />
          <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
        </svg>
      )}
    </button>
  )
}

function NavBar({ theme, onToggleTheme }) {
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
          <NavLink
            to="/patient"
            className={({ isActive }) =>
              isActive
                ? 'nav-active-link text-[11px] tracking-widest font-mono !text-red-400'
                : 'text-[11px] tracking-widest font-mono px-4 py-1.5 text-red-500/80 hover:text-red-400 transition-colors duration-150 rounded'
            }
          >
            I NEED BLOOD
          </NavLink>
        </nav>

        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
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
        <Route path="/patient" element={<PatientPortal />} />
      </Routes>
    </div>
  )
}

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem(THEME_KEY) || 'dark')

  useEffect(() => {
    document.documentElement.classList.toggle('light', theme === 'light')
    localStorage.setItem(THEME_KEY, theme)
  }, [theme])

  const toggleTheme = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'))

  return (
    <HashRouter>
      <div className="min-h-screen bg-[#06060f]">
        <NavBar theme={theme} onToggleTheme={toggleTheme} />
        <AnimatedRoutes />
      </div>
    </HashRouter>
  )
}
