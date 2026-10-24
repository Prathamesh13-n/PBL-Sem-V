import { useEffect, useState } from 'react'
import apiClient from '../api/client'

const ICONS = { pass: '✔', warn: '!', fail: '✖', info: 'i' }

export default function SecurityCheck({ requestId }) {
  const [result, setResult] = useState(null)

  useEffect(() => {
    apiClient
      .get(`/requests/${requestId}/security`)
      .then((res) => setResult(res.data))
      .catch(() => {})
  }, [requestId])

  if (!result) return null

  const tone = result.score >= 85 ? 'good' : result.score >= 60 ? 'medium' : 'high'

  return (
    <div className="detail-card security-card">
      <div className="security-head">
        <h2 className="section-title">Security Check</h2>
        <span className={`security-score security-${tone}`}>
          {result.score}/100 · {result.level}
        </span>
      </div>
      <ul className="security-list">
        {result.findings.map((f) => (
          <li key={f.check} className={`security-item sec-${f.status}`}>
            <span className="security-icon">{ICONS[f.status]}</span>
            <div>
              <strong>{f.title}</strong>
              <span>{f.detail}</span>
            </div>
          </li>
        ))}
      </ul>
      <p className="form-subtitle">
        Rule-based check of the Terraform configuration and the request. It does not
        scan the running server.
      </p>
    </div>
  )
}
