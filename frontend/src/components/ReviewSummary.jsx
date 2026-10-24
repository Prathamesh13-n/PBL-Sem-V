import { useEffect, useState } from 'react'
import apiClient from '../api/client'

const HIGH_COST_INR = 500

function timeLabel(hours) {
  if (!hours) return '—'
  const d = Math.floor(hours / 24)
  const h = hours % 24
  if (d === 0) return `${h} hour${h === 1 ? '' : 's'}`
  if (h === 0) return `${d} day${d === 1 ? '' : 's'}`
  return `${d} day${d === 1 ? '' : 's'} ${h} hour${h === 1 ? '' : 's'}`
}

// Day 29: recommendation + cost + security on one card
export default function ReviewSummary({ request, isAdmin }) {
  const [security, setSecurity] = useState(null)

  useEffect(() => {
    apiClient
      .get(`/requests/${request.id}/security`)
      .then((res) => setSecurity(res.data))
      .catch(() => {})
  }, [request.id])

  const cost = request.estimated_cost ? Number(request.estimated_cost) : null
  const score = security ? security.score : request.security_score
  const tone = score == null ? 'medium' : score >= 85 ? 'good' : score >= 60 ? 'medium' : 'high'

  const warnings = []
  if (cost !== null && cost > HIGH_COST_INR) {
    warnings.push(`High estimated cost (₹${cost.toFixed(2)}). Check that the time is really needed.`)
  }
  if (security) {
    security.findings
      .filter((f) => f.status === 'warn' || f.status === 'fail')
      .forEach((f) => warnings.push(`${f.title}: ${f.detail}`))
  }

  return (
    <div className="detail-card review-card">
      <h2 className="section-title">Review summary</h2>
      {isAdmin && request.status === 'pending' && (
        <p className="form-subtitle">Check these four points before you approve.</p>
      )}
      <div className="review-grid">
        <div className="review-tile">
          <small>Recommended instance</small>
          <strong>{request.instance_type || '—'}</strong>
          <span>{request.workload_level} workload</span>
        </div>
        <div className="review-tile">
          <small>Time requested</small>
          <strong>{timeLabel(request.duration_hours)}</strong>
          <span>auto-destroyed after this</span>
        </div>
        <div className="review-tile">
          <small>Estimated cost</small>
          <strong>{cost !== null ? `₹${cost.toFixed(2)}` : '—'}</strong>
          <span>approximate, AWS bills the real cost</span>
        </div>
        <div className={`review-tile review-${tone}`}>
          <small>Security score</small>
          <strong>{score != null ? `${score}/100` : '—'}</strong>
          <span>{security ? security.level : ''}</span>
        </div>
      </div>
      {warnings.length > 0 && (
        <ul className="review-warnings">
          {warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </div>
  )
}