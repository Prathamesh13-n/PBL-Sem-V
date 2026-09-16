import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import apiClient from '../api/client'

const STATUS_LABELS = {
  pending: 'Pending',
  approved: 'Approved',
  rejected: 'Rejected',
  provisioning: 'Provisioning',
  provisioned: 'Provisioned',
  failed: 'Failed',
}

function statusBadgeClass(status) {
  return `status-badge status-${status}`
}

function Dashboard() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    loadRequests()
  }, [])

  function loadRequests() {
    setLoading(true)
    apiClient
      .get('/requests')
      .then((res) => setRequests(res.data))
      .catch(() => setError('Could not load your requests. Please try refreshing.'))
      .finally(() => setLoading(false))
  }

  function handleLogout() {
    logout()
    navigate('/login')
  }

  // Compute a per-user "display number" — each user's own first-ever
  // request is #1, second is #2, etc. This is separate from the database
  // id (used internally for admin actions and URLs), since showing the
  // raw global id (e.g. #4) is confusing to a user who's only made one
  // request themselves. For admins, who see everyone's requests mixed
  // together, this numbering isn't meaningful, so they see the real id.
  const isAdmin = user?.role === 'admin'
  const sortedAscending = [...requests].sort(
    (a, b) => new Date(a.created_at) - new Date(b.created_at)
  )
  const displayNumberById = {}
  sortedAscending.forEach((r, index) => {
    displayNumberById[r.id] = index + 1
  })
  const counts = {
    total: requests.length,
    pending: requests.filter((r) => r.status === 'pending').length,
    approved: requests.filter((r) => r.status === 'approved').length,
    rejected: requests.filter((r) => r.status === 'rejected').length,
    provisioned: requests.filter((r) => r.status === 'provisioned').length,
  }

  return (
    <div className="dashboard-page">
      <div className="dashboard-topbar">
        <span className="wordmark">cloud-provisioning-portal</span>
        <span className="wordmark">{user?.email}</span>
      </div>

      <div className="dashboard-body">
        <div className="dashboard-header">
          <div>
            <h1>Welcome, {user?.full_name}</h1>
            <p className="role-tag">role: {user?.role}</p>
          </div>
          <div className="header-actions">
            <button className="primary-btn" onClick={() => navigate('/requests/new')}>
              + New Request
            </button>
            <button className="secondary-btn" onClick={handleLogout}>
              Logout
            </button>
          </div>
        </div>

        {error && <div className="error-box">{error}</div>}

        <div className="summary-cards">
          <SummaryCard label="TOTAL" value={counts.total} />
          <SummaryCard label="PENDING" value={counts.pending} />
          <SummaryCard label="APPROVED" value={counts.approved} />
          <SummaryCard label="REJECTED" value={counts.rejected} />
          <SummaryCard label="PROVISIONED" value={counts.provisioned} />
        </div>

        <h2 className="section-title">Recent Requests</h2>

        {loading ? (
          <p className="loading-text">loading...</p>
        ) : requests.length === 0 ? (
          <p className="empty-text">
            no requests yet — click "+ New Request" to submit your first one.
          </p>
        ) : (
          <table className="requests-table">
            <thead>
              <tr>
                <th>id</th>
                <th>instance</th>
                <th>os</th>
                <th>region</th>
                <th>status</th>
                <th>created</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((req) => (
                <tr
                  key={req.id}
                  className="clickable-row"
                  onClick={() => navigate(`/requests/${req.id}`)}
                >
                  <td>#{isAdmin ? req.id : displayNumberById[req.id]}</td>
                  <td>{req.instance_type || '—'}</td>
                  <td>{req.os}</td>
                  <td>{req.region}</td>
                  <td>
                    <span className={statusBadgeClass(req.status)}>
                      {STATUS_LABELS[req.status] || req.status}
                    </span>
                  </td>
                  <td>{new Date(req.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function SummaryCard({ label, value }) {
  return (
    <div className="summary-card">
      <div className="summary-value">{value}</div>
      <div className="summary-label">{label}</div>
    </div>
  )
}

export default Dashboard