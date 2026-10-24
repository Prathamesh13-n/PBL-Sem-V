import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import apiClient from '../api/client'
import DeploymentInfo from '../components/DeploymentInfo'
import AppLayout from '../components/AppLayout'
import SecurityCheck from '../components/SecurityCheck'
import FlowSteps from '../components/FlowSteps'
import ReviewSummary from '../components/ReviewSummary'

const STATUS_LABELS = {
  pending: 'Pending',
  approved: 'Approved',
  rejected: 'Rejected',
  provisioning: 'Provisioning',
  provisioned: 'Provisioned',
  destroyed: 'Destroyed',
  failed: 'Failed',
}

const REJECT_REASONS = [
  'Instance is not needed for this purpose',
  'Estimated cost is too high',
  'Requested duration is too long',
  'Security concern with the request',
  'Purpose is missing or unclear',
  'Other',
]

function durationLabel(hours) {
  if (!hours) return 'Default (2 hours)'
  const d = Math.floor(hours / 24)
  const h = hours % 24
  if (d === 0) return `${h} hour${h === 1 ? '' : 's'}`
  if (h === 0) return `${d} day${d === 1 ? '' : 's'}`
  return `${d} day${d === 1 ? '' : 's'} ${h} hour${h === 1 ? '' : 's'}`
}

function statusBadgeClass(status) {
  return `status-badge status-${status}`
}

function RequestDetail() {
  const { id } = useParams()
  const { user } = useAuth()

  const [request, setRequest] = useState(null)
  const [displayNumber, setDisplayNumber] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [actionLoading, setActionLoading] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [rejectPreset, setRejectPreset] = useState(REJECT_REASONS[0])
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

  const handleApprove = () => {
    // warn the admin about a risky or expensive request before approving
    const risky = request && request.security_score != null && request.security_score < 60
    const costly = request && Number(request.estimated_cost) > 500
    if (risky || costly) {
      const why = [risky && 'low security score', costly && 'high estimated cost']
        .filter(Boolean)
        .join(' and ')
      if (!window.confirm(`This request has a ${why}. Approve it anyway?`)) return
    }
    runAction(() => apiClient.patch(`/requests/${id}/approve`))
  }

  const handleReject = () => {
    const note = rejectReason.trim()
    if (rejectPreset === 'Other' && note.length < 5) {
      setActionError('Please write a reason of at least 5 characters.')
      return
    }
    const reason = rejectPreset === 'Other' ? note : note ? `${rejectPreset}. ${note}` : rejectPreset
    runAction(() => apiClient.patch(`/requests/${id}/reject`, { reason }))
  }

  const handleStartProvisioning = () =>
    runAction(() => apiClient.patch(`/requests/${id}/start-provisioning`))

  const handleDestroy = () => {
    if (!window.confirm('Destroy the real EC2 instance for this request?')) return
    runAction(() => apiClient.post(`/requests/${id}/destroy`))
  }

  const isAdmin = user?.role === 'admin'

  return (
    <AppLayout>
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

            <FlowSteps status={request.status} />

            {request.status === 'rejected' && (
              <div className="rejection-card">
                <div className="rejection-icon">✖</div>
                <div>
                  <h2 className="section-title">Request rejected</h2>
                  <p className="rejection-reason">
                    {request.rejection_reason || 'No reason was recorded for this decision.'}
                  </p>
                  {request.reviewed_at && (
                    <small>Reviewed on {new Date(request.reviewed_at).toLocaleString()}</small>
                  )}
                  {!isAdmin && (
                    <small className="rejection-hint">
                      You can submit a new request with changes based on this feedback.
                    </small>
                  )}
                </div>
              </div>
            )}

            <ReviewSummary request={request} isAdmin={isAdmin} />

            <div className="detail-card">
              <DetailRow label="Instance Name" value={request.instance_name || '—'} />
              <DetailRow label="Resource Type" value={request.resource_type} />
              <DetailRow label="Time Requested" value={durationLabel(request.duration_hours)} />
              <DetailRow label="Workload Level" value={request.workload_level} />
              <DetailRow label="Instance Type" value={request.instance_type || 'Not assigned yet'} />
              <DetailRow label="Operating System" value={request.os} />
              <DetailRow label="Region" value={request.region} />
              <DetailRow label="Storage" value={`${request.storage_gb} GB`} />
              <DetailRow label="Purpose" value={request.purpose || '—'} />
              <DetailRow
                label="Estimated Cost (approx.)"
                value={request.estimated_cost ? `₹${request.estimated_cost}` : 'Not calculated yet'}
              />
              <DetailRow
                label="Security Score"
                value={request.security_score !== null ? `${request.security_score}/100` : 'Not calculated yet'}
              />
              <DetailRow label="Created" value={new Date(request.created_at).toLocaleString()} />
            </div>

            <SecurityCheck requestId={request.id} />

            <DeploymentInfo
              requestId={request.id}
              status={request.status}
              onChange={loadRequest}
            />

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

                  {request.status === 'failed' && (
                    <button
                      className="primary-btn"
                      onClick={handleStartProvisioning}
                      disabled={actionLoading}
                    >
                      Retry Provisioning
                    </button>
                  )}

                  {request.status === 'provisioned' && (
                    <button
                      className="danger-btn"
                      onClick={handleDestroy}
                      disabled={actionLoading}
                    >
                      Destroy Instance
                    </button>
                  )}

                  {['rejected', 'provisioning', 'destroyed'].includes(request.status) && (
                    <p className="empty-text">No further actions available for this status.</p>
                  )}
                </div>

                {showRejectBox && (
                  <div className="reject-box">
                    <label htmlFor="reject-preset">Reason for rejection</label>
                    <select
                      id="reject-preset"
                      value={rejectPreset}
                      onChange={(e) => setRejectPreset(e.target.value)}
                    >
                      {REJECT_REASONS.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                    <label htmlFor="reason">
                      {rejectPreset === 'Other' ? 'Describe the reason' : 'Additional note (optional)'}
                    </label>
                    <textarea
                      id="reason"
                      rows={2}
                      maxLength={250}
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="The user will see this message."
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
    </AppLayout>
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