import { useEffect, useState } from 'react'
import api from '../api/client'

// Shows the real EC2 result for a request. Polls every 5 s while provisioning.
function timeLeft(expiresAt, now) {
  const ms = new Date(expiresAt).getTime() - now
  if (ms <= 0) return 'any moment now'
  const mins = Math.floor(ms / 60000)
  const d = Math.floor(mins / 1440)
  const h = Math.floor((mins % 1440) / 60)
  const m = mins % 60
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export default function DeploymentInfo({ requestId, status, onChange }) {
  const [dep, setDep] = useState(null)
  const [now, setNow] = useState(Date.now())

  // refresh the countdown every 30 seconds
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    let timer
    let last = null
    const load = async () => {
      try {
        const res = await api.get(`/requests/${requestId}/deployment`)
        setDep(res.data)
        const cur = res.data.deployment_status
        if (last && last !== cur && onChange) onChange()
        last = cur
        if (cur === 'provisioning') timer = setTimeout(load, 5000)
      } catch {
        /* ignore: panel simply stays hidden */
      }
    }
    load()
    return () => clearTimeout(timer)
  }, [requestId, status])

  if (!dep || !dep.deployment_status) return null
  const s = dep.deployment_status

  return (
    <div style={{ marginTop: 20, padding: 16, border: '1px solid #d1d5db', borderRadius: 10, background: '#fff', color: '#111827' }}>
      <h3 style={{ margin: '0 0 10px' }}>AWS deployment</h3>
      <p style={{ margin: '4px 0' }}>Status: <b>{s}</b></p>
      {s === 'provisioning' && <p style={{ margin: '4px 0' }}>Terraform is creating your instance. This takes about a minute...</p>}
      {dep.instance_id && <p style={{ margin: '4px 0' }}>Instance ID: <code>{dep.instance_id}</code></p>}
      {dep.public_ip && s !== 'destroyed' && <p style={{ margin: '4px 0' }}>Public IP: <code>{dep.public_ip}</code></p>}
      {dep.expires_at && s === 'provisioned' && (
        <p style={{ margin: '4px 0', color: '#b45309' }}>
          Auto-destroys in <b>{timeLeft(dep.expires_at, now)}</b>
        </p>
      )}
      {dep.provisioned_at && <p style={{ margin: '4px 0' }}>Provisioned: {new Date(dep.provisioned_at).toLocaleString()}</p>}
      {dep.destroyed_at && <p style={{ margin: '4px 0' }}>Destroyed: {new Date(dep.destroyed_at).toLocaleString()}</p>}
      {dep.error_message && (
        <pre style={{ margin: '8px 0 0', padding: 10, background: '#fee2e2', color: '#991b1b', borderRadius: 8, whiteSpace: 'pre-wrap', fontSize: 12 }}>
          {dep.error_message}
        </pre>
      )}
    </div>
  )
}