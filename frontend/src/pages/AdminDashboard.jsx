import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import './admin.css'

const STATUSES = ['pending', 'approved', 'provisioning', 'provisioned', 'destroyed', 'rejected', 'failed']
const COLORS = {
  pending: '#d97706', approved: '#2563eb', provisioning: '#7c3aed',
  provisioned: '#059669', destroyed: '#6b7280', rejected: '#dc2626', failed: '#9f1239',
}

function Donut({ counts, total }) {
  const r = 52, c = 2 * Math.PI * r
  let offset = 0
  return (
    <svg viewBox="0 0 140 140" className="donut" role="img" aria-label="Requests by status">
      <circle cx="70" cy="70" r={r} fill="none" stroke="#e5e7eb" strokeWidth="18" />
      {total > 0 && STATUSES.map((s) => {
        const len = (counts[s] / total) * c
        const el = counts[s] > 0 && (
          <circle key={s} cx="70" cy="70" r={r} fill="none" stroke={COLORS[s]} strokeWidth="18"
            strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-offset} transform="rotate(-90 70 70)" />
        )
        offset += len
        return el
      })}
      <text x="70" y="68" textAnchor="middle" className="donut-total">{total}</text>
      <text x="70" y="86" textAnchor="middle" className="donut-label">requests</text>
    </svg>
  )
}

export default function AdminDashboard() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [requests, setRequests] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = async () => {
    try {
      setError('')
      const res = await api.get('/requests')
      setRequests(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Could not load requests. Is the backend running?')
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  // refresh every 5 seconds while any request is still provisioning
  const anyProvisioning = requests.some((r) => r.status === 'provisioning')
  useEffect(() => {
    if (!anyProvisioning) return
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [anyProvisioning])

  const counts = useMemo(() => {
    const c = Object.fromEntries(STATUSES.map((s) => [s, 0]))
    requests.forEach((r) => { if (c[r.status] !== undefined) c[r.status]++ })
    return c
  }, [requests])

  const visible = filter === 'all' ? requests : requests.filter((r) => r.status === filter)

  const act = async (id, action) => {
    let body
    if (action === 'destroy' && !window.confirm('Destroy the real EC2 instance for this request?')) return
    if (action === 'reject') {
      const reason = window.prompt('Reason for rejection (optional):')
      if (reason === null) return
      body = { reason }
    }
    setBusyId(id)
    try {
      if (action === 'destroy') await api.post(`/requests/${id}/destroy`)
      else await api.patch(`/requests/${id}/${action}`, body)
      await load()
    } catch (e) {
      setError(e.response?.data?.detail || 'Action failed')
    } finally { setBusyId(null) }
  }

  return (
    <div className="adm-shell">
      <aside className="adm-side">
        <div className="adm-brand">EC2 Portal<span>Admin</span></div>
        <nav>
          <Link className="active" to="/admin">Overview</Link>
          <Link to="/dashboard">My requests</Link>
          <Link to="/requests/new">New request</Link>
        </nav>
        <div className="adm-user">
          <div>{user?.email}</div>
          <button onClick={() => { logout(); navigate('/login') }}>Log out</button>
        </div>
      </aside>

      <main className="adm-main">
        <h1>Admin dashboard</h1>
        {error && <div className="adm-error">{error}</div>}

        <section className="adm-cards">
          {STATUSES.map((s) => (
            <button key={s} className={`adm-card ${filter === s ? 'on' : ''}`}
              onClick={() => setFilter(filter === s ? 'all' : s)}>
              <span className="dot" style={{ background: COLORS[s] }} />
              <strong>{counts[s]}</strong>
              <small>{s}</small>
            </button>
          ))}
        </section>

        <section className="adm-panel adm-chart">
          <Donut counts={counts} total={requests.length} />
          <ul>
            {STATUSES.map((s) => (
              <li key={s}><span className="dot" style={{ background: COLORS[s] }} />{s}<b>{counts[s]}</b></li>
            ))}
          </ul>
        </section>

        <section className="adm-panel">
          <div className="adm-bar">
            <h2>All requests</h2>
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">All statuses</option>
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          {loading ? <p>Loading...</p> : visible.length === 0 ? <p>No requests found.</p> : (
            <div className="table-scroll">
              <table className="adm-table">
                <thead><tr>
                  <th>ID</th><th>Name</th><th>User</th><th>Time</th><th>Instance</th><th>OS</th><th>Cost/mo</th><th>Status</th><th>Actions</th>
                </tr></thead>
                <tbody>
                  {visible.map((r) => (
                    <tr key={r.id}>
                      <td><Link to={`/requests/${r.id}`}>#{r.id}</Link></td>
                      <td>{r.instance_name || '-'}</td>
                      <td>{r.user_id}</td>
                      <td style={r.duration_hours > 168 ? { color: '#b45309', fontWeight: 700 } : undefined}
                          title={r.duration_hours > 168 ? 'Long request: check the price before approving' : undefined}>
                        {r.duration_hours
                          ? (r.duration_hours >= 24
                              ? `${Math.floor(r.duration_hours / 24)}d${r.duration_hours % 24 ? ` ${r.duration_hours % 24}h` : ''}`
                              : `${r.duration_hours}h`)
                          : '-'}
                      </td>
                      <td>{r.instance_type}</td>
                      <td>{r.os}</td>
                      <td>{r.estimated_cost != null ? `$${Number(r.estimated_cost).toFixed(2)}` : '-'}</td>
                      <td><span className="pill" style={{ background: COLORS[r.status] }}>{r.status}</span></td>
                      <td className="acts">
                        {r.status === 'pending' && (<>
                          <button disabled={busyId === r.id} onClick={() => act(r.id, 'approve')}>Approve</button>
                          <button className="danger" disabled={busyId === r.id} onClick={() => act(r.id, 'reject')}>Reject</button>
                        </>)}
                        {(r.status === 'approved' || r.status === 'failed') && (
                          <button disabled={busyId === r.id} onClick={() => act(r.id, 'start-provisioning')}>
                            {r.status === 'failed' ? 'Retry' : 'Provision'}
                          </button>
                        )}
                        {r.status === 'provisioned' && (
                          <button className="danger" disabled={busyId === r.id} onClick={() => act(r.id, 'destroy')}>Destroy</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}