const API_BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const message = payload.detail || `Request failed with status ${response.status}`
    throw new Error(message)
  }
  return payload
}

function queryString(params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value)
  })
  const rendered = query.toString()
  return rendered ? `?${rendered}` : ''
}

export const api = {
  health: () => request('/api/health'),
  createCase: (body) => request('/api/visitors', { method: 'POST', body: JSON.stringify(body) }),
  getCase: (caseId) => request(`/api/visitors/${encodeURIComponent(caseId)}`),
  getCases: (params = {}) => request(`/api/cases${queryString(params)}`),
  getCaseSummary: () => request('/api/cases/summary'),
  getReviews: () => request('/api/reviews'),
  getAudit: (caseId) => request(`/api/audits/${encodeURIComponent(caseId)}`),
  getEvidence: (caseId) => request(`/api/exports/cases/${encodeURIComponent(caseId)}`),
  getProof: (caseId) => request(`/api/proof/${encodeURIComponent(caseId)}`),
  verifyProof: (caseId) => request(`/api/proof/${encodeURIComponent(caseId)}/verify`),
  verifyPortableProof: (packet) => request('/api/proof/verify-portable', { method: 'POST', body: JSON.stringify(packet) }),
  runProofTamperDemo: (caseId) => request(`/api/proof/${encodeURIComponent(caseId)}/tamper-demo`),
  getReplayScenarios: () => request('/api/replay/scenarios'),
  runReplay: (caseId, scenario) => request(`/api/replay/${encodeURIComponent(caseId)}`, { method: 'POST', body: JSON.stringify({ scenario }) }),
  getLoopContracts: () => request('/api/loops/contracts'),
  getLoopRuns: (caseId = '') => request(`/api/loops/runs${queryString({ case_id: caseId })}`),
  getLoopSummary: (caseId = '') => request(`/api/loops/summary${queryString({ case_id: caseId })}`),
  simulateLoop: (scenario) => request('/api/loops/simulate', { method: 'POST', body: JSON.stringify({ scenario }) }),
  decide: (caseId, action, body) =>
    request(`/api/reviews/${encodeURIComponent(caseId)}/${action}`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  runEvaluation: () => request('/api/evaluation/run', { method: 'POST' }),
  runAgentEvaluation: () => request('/api/evaluation/agent/run', { method: 'POST' }),
  runSystemCheck: () => request('/api/system/check', { method: 'POST' }),
  resetDemo: () => request('/api/demo/reset', { method: 'DELETE' }),
}

export function downloadJson(filename, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
