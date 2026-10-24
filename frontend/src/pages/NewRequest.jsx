import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient from '../api/client'
import AppLayout from '../components/AppLayout'

const OS_OPTIONS = ['Amazon Linux 2', 'Ubuntu 22.04']
const REGION_OPTIONS = ['ap-south-1']
const WORKLOAD_OPTIONS = [
  { value: 'low', label: 'Low', hint: 'Light usage — testing, small scripts' },
  { value: 'medium', label: 'Medium', hint: 'Moderate usage — small apps, dev environments' },
  { value: 'high', label: 'High', hint: 'Heavy usage — production workloads' },
]

const MAX_CUSTOM_DAYS = 90

// "2026-10-17T11:30" in the user's local time, as <input type="datetime-local"> wants it
function toLocalInput(date) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function describeHours(hours) {
  const d = Math.floor(hours / 24)
  const h = hours % 24
  if (d === 0) return `${h} hour${h === 1 ? '' : 's'}`
  if (h === 0) return `${d} day${d === 1 ? '' : 's'}`
  return `${d} day${d === 1 ? '' : 's'} ${h} hour${h === 1 ? '' : 's'}`
}

function NewRequest() {
  const navigate = useNavigate()

  const [instanceName, setInstanceName] = useState('')
  const [durationHours, setDurationHours] = useState(2)
  const [durationOptions, setDurationOptions] = useState([])
  const [useCustom, setUseCustom] = useState(false)
  const [customEnd, setCustomEnd] = useState('')
  const [customPrice, setCustomPrice] = useState(null)
  const [recommendation, setRecommendation] = useState(null)
  const [preview, setPreview] = useState(null)
  const [workloadLevel, setWorkloadLevel] = useState('low')
  const [os, setOs] = useState(OS_OPTIONS[0])
  const [region, setRegion] = useState(REGION_OPTIONS[0])
  const [storageGb, setStorageGb] = useState(20)
  const [purpose, setPurpose] = useState('')

  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // load the time options with their approximate price; refresh when storage changes
  useEffect(() => {
    const gb = Number(storageGb)
    if (!gb || gb < 8 || gb > 30) return
    apiClient
      .get('/requests/duration-options', { params: { storage_gb: gb, workload: workloadLevel } })
      .then((res) => setDurationOptions(res.data))
      .catch(() => {})
  }, [storageGb, workloadLevel])

  // rule-based recommendation for the chosen workload level
  useEffect(() => {
    const gb = Number(storageGb)
    if (!gb || gb < 8 || gb > 30) return
    apiClient
      .get('/requests/recommendation', { params: { workload: workloadLevel, storage_gb: gb } })
      .then((res) => setRecommendation(res.data))
      .catch(() => {})
  }, [workloadLevel, storageGb])

  // hours between now and the chosen custom end date (rounded up)
  const customHours = customEnd
    ? Math.ceil((new Date(customEnd).getTime() - Date.now()) / 3600000)
    : 0
  const customValid = customHours >= 1 && customHours <= MAX_CUSTOM_DAYS * 24
  const effectiveHours = useCustom ? customHours : durationHours

  // price for the custom time
  useEffect(() => {
    setCustomPrice(null)
    const gb = Number(storageGb)
    if (!useCustom || !customValid || !gb || gb < 8 || gb > 30) return
    apiClient
      .get('/requests/estimate', { params: { storage_gb: gb, hours: customHours, workload: workloadLevel } })
      .then((res) => setCustomPrice(res.data))
      .catch(() => {})
  }, [useCustom, customHours, customValid, storageGb, workloadLevel])

  // Day 29: one combined review (recommendation + cost + security) before submitting
  useEffect(() => {
    const gb = Number(storageGb)
    const okHours = effectiveHours >= 1 && effectiveHours <= MAX_CUSTOM_DAYS * 24
    if (!okHours || !gb || gb < 8 || gb > 30) {
      setPreview(null)
      return
    }
    const timer = setTimeout(() => {
      apiClient
        .get('/requests/preview', {
          params: { workload: workloadLevel, storage_gb: gb, hours: effectiveHours, purpose },
        })
        .then((res) => setPreview(res.data))
        .catch(() => setPreview(null))
    }, 400)
    return () => clearTimeout(timer)
  }, [workloadLevel, storageGb, effectiveHours, purpose])

  const selectedOption = durationOptions.find((o) => o.hours === durationHours)
  const minInput = toLocalInput(new Date(Date.now() + 3600000))
  const maxInput = toLocalInput(new Date(Date.now() + MAX_CUSTOM_DAYS * 24 * 3600000))

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (useCustom && !customValid) {
      setError(`Please choose an end date between 1 hour and ${MAX_CUSTOM_DAYS} days from now. For more than ${MAX_CUSTOM_DAYS} days, please contact the admin.`)
      return
    }
    setSubmitting(true)

    try {
      await apiClient.post('/requests', {
        instance_name: instanceName.trim(),
        duration_hours: effectiveHours,
        workload_level: workloadLevel,
        os,
        region,
        storage_gb: Number(storageGb),
        purpose: purpose || null,
      })
      navigate('/dashboard')
    } catch (err) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        setError(detail)
      } else if (Array.isArray(detail) && detail.length > 0) {
        setError(detail.map((d) => d.msg.replace('Value error, ', '')).join(' · '))
      } else {
        setError('Could not submit the request. Please check the fields and try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AppLayout>
      <div className="dashboard-body">
        <h1 className="form-title">New EC2 Resource Request</h1>
        <p className="form-subtitle">
          Fill in the five steps below. The portal recommends an instance, estimates the
          cost and checks security. An admin then reviews your request, and the instance
          is destroyed automatically when your time is up.
        </p>

        {error && <div className="error-box">{error}</div>}

        <form className="request-form sectioned" onSubmit={handleSubmit}>
          {/* 1 ---------------------------------------------------------- */}
          <section className="form-section">
            <div className="form-section-head">
              <span className="step-num">1</span>
              <div>
                <h2>Basic details</h2>
                <p>Name your instance and explain what you need it for.</p>
              </div>
            </div>
            <label htmlFor="instance-name">Instance name</label>
            <input
              id="instance-name"
              type="text"
              maxLength={40}
              placeholder="e.g. my-website-test"
              value={instanceName}
              onChange={(e) => setInstanceName(e.target.value)}
              required
            />
            <label htmlFor="purpose">Purpose / justification</label>
            <textarea
              id="purpose"
              rows={3}
              placeholder="e.g. Hosting a small Node.js API for a college project demo"
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
            />
            <small className="field-hint">
              A clear purpose helps the admin approve faster and improves your security score.
            </small>
          </section>

          {/* 2 ---------------------------------------------------------- */}
          <section className="form-section">
            <div className="form-section-head">
              <span className="step-num">2</span>
              <div>
                <h2>Duration</h2>
                <p>How long do you need it? The price below is for this time only.</p>
              </div>
            </div>
            <div className="workload-options">
              {durationOptions.map((opt) => (
                <label
                  key={opt.hours}
                  className={`workload-option ${!useCustom && durationHours === opt.hours ? 'selected' : ''}`}
                >
                  <input
                    type="radio"
                    name="duration"
                    value={opt.hours}
                    checked={!useCustom && durationHours === opt.hours}
                    onChange={() => {
                      setUseCustom(false)
                      setDurationHours(opt.hours)
                    }}
                  />
                  <div>
                    <strong>{opt.label}</strong>
                    <span>≈ ₹{opt.inr.toFixed(2)}</span>
                  </div>
                </label>
              ))}

              <label className={`workload-option ${useCustom ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="duration"
                  checked={useCustom}
                  onChange={() => setUseCustom(true)}
                />
                <div>
                  <strong>Custom end date and time</strong>
                  <span>Up to {MAX_CUSTOM_DAYS} days. Need more than {MAX_CUSTOM_DAYS} days? Please contact the admin.</span>
                  <input
                    type="datetime-local"
                    value={customEnd}
                    min={minInput}
                    max={maxInput}
                    onFocus={() => setUseCustom(true)}
                    onChange={(e) => {
                      setUseCustom(true)
                      setCustomEnd(e.target.value)
                    }}
                  />
                </div>
              </label>
            </div>

            {!useCustom && selectedOption && (
              <p className="cost-line">
                Approximate cost for {selectedOption.label}: <strong>₹{selectedOption.inr.toFixed(2)}</strong>{' '}
                (about ${selectedOption.usd.toFixed(2)}). Estimate only; the real bill comes from AWS.
              </p>
            )}
            {useCustom && !customEnd && (
              <p className="cost-line">Pick an end date and time to see the approximate cost.</p>
            )}
            {useCustom && customEnd && !customValid && (
              <p className="cost-line cost-warn">
                The end must be between 1 hour and {MAX_CUSTOM_DAYS} days from now. If you need
                more than {MAX_CUSTOM_DAYS} days, please contact the admin.
              </p>
            )}
            {useCustom && customValid && (
              <p className="cost-line">
                Your instance will run for about {describeHours(customHours)}, counted from when it
                is created.
                {customPrice && (
                  <>
                    {' '}Approximate cost: <strong>₹{customPrice.inr.toFixed(2)}</strong> (about $
                    {customPrice.usd.toFixed(2)}).
                  </>
                )}{' '}
                Estimate only; the real bill comes from AWS.
              </p>
            )}
          </section>

          {/* 3 ---------------------------------------------------------- */}
          <section className="form-section">
            <div className="form-section-head">
              <span className="step-num">3</span>
              <div>
                <h2>Workload and recommendation</h2>
                <p>Tell us how heavy the usage will be. The portal picks the instance size.</p>
              </div>
            </div>
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

            {recommendation && (
              <div className="recommend-box">
                <div className="recommend-badge">Recommended</div>
                <h3>{recommendation.instance_type}</h3>
                <p className="recommend-spec">
                  {recommendation.vcpu} vCPU · {recommendation.memory_gb} GiB memory
                </p>
                <p>{recommendation.reason}</p>
                <p className="recommend-ref">
                  Reference price (full month, 24x7):{' '}
                  <strong>₹{recommendation.monthly_inr.toFixed(2)}</strong> (about $
                  {recommendation.monthly_usd.toFixed(2)})
                </p>
                <small>
                  For comparison only. You pay for the time you choose above, not a full month.
                  Based on approximate ap-south-1 (Mumbai) prices.
                </small>
              </div>
            )}
          </section>

          {/* 4 ---------------------------------------------------------- */}
          <section className="form-section">
            <div className="form-section-head">
              <span className="step-num">4</span>
              <div>
                <h2>Configuration</h2>
                <p>Operating system, region and disk size.</p>
              </div>
            </div>
            <div className="config-grid">
              <div>
                <label htmlFor="os">Operating system</label>
                <select id="os" value={os} onChange={(e) => setOs(e.target.value)}>
                  {OS_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="region">Region</label>
                <select id="region" value={region} onChange={(e) => setRegion(e.target.value)}>
                  {REGION_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="storage">Storage (GB, 8 to 30)</label>
                <input
                  id="storage"
                  type="number"
                  min={8}
                  max={30}
                  value={storageGb}
                  onChange={(e) => setStorageGb(e.target.value)}
                  required
                />
              </div>
            </div>
          </section>

          {/* 5 ---------------------------------------------------------- */}
          <section className="form-section">
            <div className="form-section-head">
              <span className="step-num">5</span>
              <div>
                <h2>Review and submit</h2>
                <p>Check the summary, then send the request for admin approval.</p>
              </div>
            </div>

            {preview ? (
              <div className="preview-box">
                <div className="review-grid">
                  <div className="review-tile">
                    <small>Instance</small>
                    <strong>{preview.recommendation.instance_type}</strong>
                    <span>{preview.recommendation.vcpu} vCPU, {preview.recommendation.memory_gb} GiB</span>
                  </div>
                  <div className="review-tile">
                    <small>Time</small>
                    <strong>{describeHours(preview.cost.hours)}</strong>
                    <span>auto-destroyed after this</span>
                  </div>
                  <div className="review-tile">
                    <small>Estimated cost</small>
                    <strong>₹{preview.cost.inr.toFixed(2)}</strong>
                    <span>about ${preview.cost.usd.toFixed(2)}</span>
                  </div>
                  <div
                    className={`review-tile review-${
                      preview.security.score >= 85 ? 'good' : preview.security.score >= 60 ? 'medium' : 'high'
                    }`}
                  >
                    <small>Security score</small>
                    <strong>{preview.security.score}/100</strong>
                    <span>{preview.security.level}</span>
                  </div>
                </div>
                {preview.security.findings.some((f) => f.status === 'warn' || f.status === 'fail') && (
                  <ul className="review-warnings">
                    {preview.security.findings
                      .filter((f) => f.status === 'warn' || f.status === 'fail')
                      .map((f) => (
                        <li key={f.check}>{f.title}</li>
                      ))}
                  </ul>
                )}
              </div>
            ) : (
              <p className="cost-line">Choose a valid time to see the summary.</p>
            )}

            <p className="flow-note">
              Request → Recommendation → Cost estimate → Security check → Admin approval →
              Terraform → AWS EC2
            </p>

            <button type="submit" className="primary-btn full-width" disabled={submitting}>
              {submitting ? 'Submitting...' : 'Submit request for approval'}
            </button>
          </section>
        </form>
      </div>
    </AppLayout>
  )
}

export default NewRequest