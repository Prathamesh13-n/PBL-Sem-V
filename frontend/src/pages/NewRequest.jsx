import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import apiClient from '../api/client'

const OS_OPTIONS = ['Amazon Linux 2', 'Ubuntu 22.04']
const REGION_OPTIONS = ['ap-south-1']
const WORKLOAD_OPTIONS = [
  { value: 'low', label: 'Low', hint: 'Light usage — testing, small scripts' },
  { value: 'medium', label: 'Medium', hint: 'Moderate usage — small apps, dev environments' },
  { value: 'high', label: 'High', hint: 'Heavy usage — production workloads' },
]

function NewRequest() {
  const navigate = useNavigate()

  const [workloadLevel, setWorkloadLevel] = useState('low')
  const [os, setOs] = useState(OS_OPTIONS[0])
  const [region, setRegion] = useState(REGION_OPTIONS[0])
  const [storageGb, setStorageGb] = useState(20)
  const [purpose, setPurpose] = useState('')

  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)

    try {
      await apiClient.post('/requests', {
        workload_level: workloadLevel,
        os,
        region,
        storage_gb: Number(storageGb),
        purpose: purpose || null,
      })
      navigate('/dashboard')
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(
        typeof detail === 'string'
          ? detail
          : 'Could not submit the request. Please check the fields and try again.'
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="dashboard-page">
      <div className="dashboard-topbar">
        <span className="wordmark">cloud-provisioning-portal</span>
        <Link to="/dashboard" className="wordmark topbar-link">
          ← back to dashboard
        </Link>
      </div>

      <div className="dashboard-body">
        <h1 className="form-title">New EC2 Resource Request</h1>
        <p className="form-subtitle">
          Instance type, cost, and security score will be calculated automatically
          once the recommendation engine is added (Day 26–28). For now, this request
          is submitted as "pending" for admin review.
        </p>

        {error && <div className="error-box">{error}</div>}

        <form className="request-form" onSubmit={handleSubmit}>
          <label>Workload Level</label>
          <div className="workload-options">
            {WORKLOAD_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`workload-option ${workloadLevel === opt.value ? 'selected' : ''}`}
              >
                <input
                  type="radio"
                  name="workload"
                  value={opt.value}
                  checked={workloadLevel === opt.value}
                  onChange={() => setWorkloadLevel(opt.value)}
                />
                <div>
                  <strong>{opt.label}</strong>
                  <span>{opt.hint}</span>
                </div>
              </label>
            ))}
          </div>

          <label htmlFor="os">Operating System</label>
          <select id="os" value={os} onChange={(e) => setOs(e.target.value)}>
            {OS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>

          <label htmlFor="region">Region</label>
          <select id="region" value={region} onChange={(e) => setRegion(e.target.value)}>
            {REGION_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>

          <label htmlFor="storage">Storage (GB)</label>
          <input
            id="storage"
            type="number"
            min={8}
            max={500}
            value={storageGb}
            onChange={(e) => setStorageGb(e.target.value)}
            required
          />

          <label htmlFor="purpose">Purpose / Justification</label>
          <textarea
            id="purpose"
            rows={3}
            placeholder="e.g. Hosting a small Node.js API for a college project demo"
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
          />

          <button type="submit" className="primary-btn full-width" disabled={submitting}>
            {submitting ? 'Submitting...' : 'Submit Request'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default NewRequest