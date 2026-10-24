import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import '../pages/admin.css'

// Sidebar + content area shared by every logged-in page.
export default function AppLayout({ children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const isAdmin = user?.role === 'admin'
  const linkClass = ({ isActive }) => (isActive ? 'active' : '')

  return (
    <div className="adm-shell">
      <aside className="adm-side">
        <div className="adm-brand">
          EC2 Portal<span>{isAdmin ? 'Admin' : 'User'}</span>
        </div>
        <nav>
          <NavLink to="/dashboard" end className={linkClass}>My requests</NavLink>
          <NavLink to="/requests/new" className={linkClass}>New request</NavLink>
          {isAdmin && <NavLink to="/admin" className={linkClass}>Admin dashboard</NavLink>}
        </nav>
        <div className="adm-user">
          <div>{user?.email}</div>
          <button
            onClick={() => {
              logout()
              navigate('/login')
            }}
          >
            Log out
          </button>
        </div>
      </aside>
      <main className="adm-main">{children}</main>
    </div>
  )
}
