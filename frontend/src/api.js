const BASE = 'https://046giqhktg.execute-api.ap-south-1.amazonaws.com/prod'

export async function findDonors(patientId) {
  const res = await fetch(`${BASE}/match`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patient_id: patientId }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  const body = typeof data.body === 'string' ? JSON.parse(data.body) : data
  if (body.error) throw new Error(body.error)
  return body
}

export async function getAdminStats() {
  const res = await fetch(`${BASE}/admin`, { cache: 'no-cache' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  return typeof data.body === 'string' ? JSON.parse(data.body) : data
}
