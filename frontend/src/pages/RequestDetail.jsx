import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
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

function RequestDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [request, setRequest] = useState(null)
  const [displayNumber, setDisplayNumber] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [actionLoading, setActionLoading] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectBox, setShowRejectBox] = useState(false)

  useEffect(() => {
    loadRequest()
  }, [id])

  function loadRequest() {
    setLoading(true)
    setError('')
    apiClient
      .get(`/requests/${id}`)
      .then((res) => {
        setRequest(res.data)
        // Only regular users need a display number — admins see the raw
        // id since they're viewing everyone's requests mixed together.
        if (user?.role !== 'admin') {
          apiClient.get('/requests').then((listRes) => {
            const sortedAscending = [...listRes.data].sort(
              (a, b) => new Date(a.created_at) - new Date(b.created_at)
            )
            const index = sortedAscending.findIndex((r) => r.id === res.data.id)
            setDisplayNumber(index >= 0 ? index + 1 : res.data.id)
          })
        }
      })
      .catch((err) => {
        if (err.response?.status === 404) {
          setError('Request not found.')
        } else if (err.response?.status === 403) {
          setError('You are not authorized to view this request.')
        } else {
          setError('Could not load this request.')
        }
      })
      .finally(() => setLoading(false))
  }

  async function runAction(actionFn) {
    setActionError('')
    setActionLoading(true)
    try {
      await actionFn()
      await loadRequest()
      setShowRejectBox(false)
      setRejectReason('')
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Action failed.')
    } finally {
      setActionLoading(false)
    }
  }

  const handleApprove = () =>
    runAction(() => apiClient.patch(`/requests/${id}/approve`))

  const handleReject = () =>
    runAction(() =>
      apiClient.patch(`/requests/${id}/reject`, { reason: rejectReason || null })
    )

  const handleStartProvisioning = () =>
    runAction(() => apiClient.patch(`/requests/${id}/start-provisioning`))

  const isAdmin = user?.role === 'admin'

  return (
    <div className="dashboard-page">
      <div className="dashboard-topbar">
        <span className="wordmark">cloud-provisioning-portal</span>
        <Link to="/dashboard" className="wordmark topbar-link">
          ← back to dashboard
        </Link>
      </div>

      <div className="dashboard-body">
        {loading && <p className="loading-text">loading...</p>}

        {error && <div className="error-box">{error}</div>}

        {request && (
          <>
            <div className="detail-header">
              <h1 className="form-title">
                Request #{isAdmin ? request.id : (displayNumber ?? '...')}
              </h1>
              <span className={statusBadgeClass(request.status)}>
                {STATUS_LABELS[request.status] || request.status}
              </span>
            </div>

            <div className="detail-card">
              <DetailRow label="Resource Type" value={request.resource_type} />
              <DetailRow label="Workload Level" value={request.workload_level} />
              <DetailRow label="Instance Type" value={request.instance_type || 'Not assigned yet'} />
              <DetailRow label="Operating System" value={request.os} />
              <DetailRow label="Region" value={request.region} />
              <DetailRow label="Storage" value={`${request.storage_gb} GB`} />
              <DetailRow label="Purpose" value={request.purpose || '—'} />
              <DetailRow
                label="Estimated Cost"
                value={request.estimated_cost ? `₹${request.estimated_cost}` : 'Not calculated yet'}
              />
              <DetailRow
                label="Security Score"
                value={request.security_score !== null ? `${request.security_score}/100` : 'Not calculated yet'}
              />
              <DetailRow label="Created" value={new Date(request.created_at).toLocaleString()} />
            </div>

            {isAdmin && (
              <div className="admin-actions">
                <h2 className="section-title">Admin Actions</h2>
                {actionError && <div className="error-box">{actionError}</div>}

                <div className="action-buttons">
                  {request.status === 'pending' && (
                    <>
                      <button
                        className="primary-btn"
                        onClick={handleApprove}
                        disabled={actionLoading}
                      >
                        Approve
                      </button>
                      <button
                        className="danger-btn"
                        onClick={() => setShowRejectBox((v) => !v)}
                        disabled={actionLoading}
                      >
                        Reject
                      </button>
                    </>
                  )}

                  {request.status === 'approved' && (
                    <button
                      className="primary-btn"
                      onClick={handleStartProvisioning}
                      disabled={actionLoading}
                    >
                      Start Provisioning
                    </button>
                  )}

                  {['rejected', 'provisioning', 'provisioned', 'failed'].includes(request.status) && (
                    <p className="empty-text">No further actions available for this status.</p>
                  )}
                </div>

                {showRejectBox && (
                  <div className="reject-box">
                    <label htmlFor="reason">Reason (optional)</label>
                    <textarea
                      id="reason"
                      rows={2}
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="Why is this request being rejected?"
                    />
                    <button
                      className="danger-btn"
                      onClick={handleReject}
                      disabled={actionLoading}
                    >
                      Confirm Reject
                    </button>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function DetailRow({ label, value }) {
  return (
    <div className="detail-row">
      <span className="detail-label">{label}</span>
      <span className="detail-value">{value}</span>
    </div>
  )
}

export default RequestDetail