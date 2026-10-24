// Day 29: shows where a request is in the final flow
// Request -> Recommendation -> Cost -> Security -> Approval -> Terraform -> AWS EC2
const STEPS = [
  'Request',
  'Recommendation',
  'Cost estimate',
  'Security check',
  'Admin approval',
  'Terraform',
  'AWS EC2',
]

// state of each step for a given request status: done | current | fail | todo
function stepStates(status) {
  const s = ['done', 'done', 'done', 'done', 'todo', 'todo', 'todo']

  if (status === 'pending') {
    s[4] = 'current'
  } else if (status === 'rejected') {
    s[4] = 'fail'
  } else {
    s[4] = 'done'
    if (status === 'approved') s[5] = 'current'
    if (status === 'provisioning') s[5] = 'current'
    if (status === 'failed') s[5] = 'fail'
    if (status === 'provisioned') {
      s[5] = 'done'
      s[6] = 'current'
    }
    if (status === 'destroyed') {
      s[5] = 'done'
      s[6] = 'done'
    }
  }
  return s
}

export default function FlowSteps({ status }) {
  const states = stepStates(status)
  return (
    <ol className="flow-steps">
      {STEPS.map((label, i) => (
        <li key={label} className={`flow-step flow-${states[i]}`}>
          <span className="flow-dot">
            {states[i] === 'done' ? '✔' : states[i] === 'fail' ? '✖' : i + 1}
          </span>
          <span className="flow-label">{label}</span>
        </li>
      ))}
    </ol>
  )
}