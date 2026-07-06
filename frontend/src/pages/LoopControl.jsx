import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'

const simulations = [
  ['pass_first', 'Pass first time', 'Goal verified on the first permitted action.'],
  ['retry_then_pass', 'Retry then pass', 'One bounded retry produces a verified result.'],
  ['no_progress', 'No-progress stop', 'Repeated output triggers a stalled terminal state.'],
  ['unauthorised_tool', 'Unauthorised tool', 'A non-permitted action is blocked before execution.'],
]

function title(value = '') {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function tone(state = '') {
  if (['success', 'approved', 'no_op'].includes(state)) return 'pass'
  if (['safe_fallback', 'escalated', 'more_information_requested'].includes(state)) return 'warning'
  if (['blocked', 'stalled', 'exhausted', 'rejected'].includes(state)) return 'danger'
  return 'neutral'
}

export default function LoopControl({ latestCaseId = '', refreshToken = 0 }) {
  const [contracts, setContracts] = useState([])
  const [cases, setCases] = useState([])
  const [selectedCaseId, setSelectedCaseId] = useState(latestCaseId)
  const [runs, setRuns] = useState([])
  const [summary, setSummary] = useState(null)
  const [selectedContract, setSelectedContract] = useState('grounded_agent_review')
  const [simulation, setSimulation] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const activeContract = useMemo(
    () => contracts.find((item) => item.name === selectedContract) || contracts[0],
    [contracts, selectedContract],
  )

  const loadBase = async () => {
    try {
      const [contractPayload, casePayload] = await Promise.all([
        api.getLoopContracts(),
        api.getCases({ limit: 100 }),
      ])
      setContracts(contractPayload.contracts || [])
      setCases(casePayload)
      setSelectedCaseId((current) => {
        if (latestCaseId && casePayload.some((item) => item.case_id === latestCaseId)) return latestCaseId
        if (current && casePayload.some((item) => item.case_id === current)) return current
        return casePayload[0]?.case_id || ''
      })
    } catch (err) {
      setError(err.message)
    }
  }

  const loadRuns = async (caseId = selectedCaseId) => {
    if (!caseId) {
      setRuns([])
      setSummary(null)
      return
    }
    try {
      const payload = await api.getLoopRuns(caseId)
      setRuns(payload.runs || [])
      setSummary(payload.summary || null)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { loadBase() }, [refreshToken])
  useEffect(() => { loadRuns(selectedCaseId) }, [selectedCaseId, refreshToken])

  const runSimulation = async (scenario) => {
    setBusy(true)
    setError('')
    try { setSimulation(await api.simulateLoop(scenario)) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <section className="loop-layout page-fill">
      <aside className="panel loop-contract-panel">
        <div className="panel__heading compact-heading">
          <div><p className="eyebrow">Loop contracts</p><h2>Bounded operating rules</h2></div>
          <span className="loop-count">{contracts.length}</span>
        </div>
        <div className="loop-contract-list panel-scroll">
          {contracts.map((contract) => (
            <button
              key={contract.name}
              className={selectedContract === contract.name ? 'active' : ''}
              onClick={() => setSelectedContract(contract.name)}
            >
              <strong>{contract.label}</strong>
              <small>{contract.agent_name}</small>
              <span>{contract.max_attempts} max attempt{contract.max_attempts === 1 ? '' : 's'}</span>
            </button>
          ))}
        </div>
        {activeContract && (
          <div className="loop-contract-detail">
            <span>Goal</span><strong>{activeContract.goal}</strong>
            <div className="loop-tool-tags">{activeContract.permitted_tools.map((tool) => <em key={tool}>{tool}</em>)}</div>
            <small>{activeContract.consequence_boundary}</small>
          </div>
        )}
      </aside>

      <article className="panel loop-run-panel">
        <div className="panel__heading compact-heading">
          <div><p className="eyebrow">Execution evidence</p><h2>Case loop trace</h2></div>
          <select value={selectedCaseId} onChange={(event) => setSelectedCaseId(event.target.value)}>
            {!cases.length && <option value="">No cases</option>}
            {cases.map((item) => <option key={item.case_id} value={item.case_id}>{item.request.visitor_name} · {item.case_id}</option>)}
          </select>
        </div>
        {error && <div className="error">{error}</div>}
        {summary && (
          <div className="loop-summary-strip">
            <div><span>Runs</span><strong>{summary.total_runs}</strong></div>
            <div><span>Bounded</span><strong>{Math.round((summary.bounded_rate || 0) * 100)}%</strong></div>
            <div><span>Retries</span><strong>{summary.total_retries}</strong></div>
            <div><span>Unauthorised</span><strong>{summary.unauthorized_tool_attempts}</strong></div>
            <div><span>No-progress stops</span><strong>{summary.no_progress_stops}</strong></div>
          </div>
        )}
        <div className="loop-run-list panel-scroll">
          {!runs.length ? <div className="empty-state">Create a case to generate loop evidence.</div> : runs.map((run, index) => (
            <div key={run.run_id} className={`loop-run-card loop-run-card--${tone(run.terminal_state)}`}>
              <div className="loop-run-index">{String(index + 1).padStart(2, '0')}</div>
              <div className="loop-run-copy">
                <div><strong>{title(run.loop_name)}</strong><span>{run.elapsed_ms} ms</span></div>
                <p>{run.goal}</p>
                <small>{run.stop_reason}</small>
              </div>
              <div className="loop-run-state">
                <span>{title(run.decision)}</span>
                <strong>{title(run.terminal_state)}</strong>
                <small>{run.attempt_number}/{run.max_attempts} attempts</small>
              </div>
            </div>
          ))}
        </div>
      </article>

      <aside className="panel loop-test-panel">
        <div><p className="eyebrow">Loop laboratory</p><h2>Stop-rule tests</h2></div>
        <p className="loop-test-intro">Demonstrate pass, bounded retry, no-progress detection and tool-permission enforcement without changing a case.</p>
        <div className="loop-simulation-list">
          {simulations.map(([id, label, detail]) => (
            <button key={id} onClick={() => runSimulation(id)} disabled={busy}>
              <strong>{label}</strong><small>{detail}</small>
            </button>
          ))}
        </div>
        {simulation ? (
          <div className={`loop-simulation-result loop-simulation-result--${tone(simulation.terminal_state)}`}>
            <span>{title(simulation.decision)}</span>
            <strong>{title(simulation.terminal_state)}</strong>
            <p>{simulation.stop_reason}</p>
            <div><small>Attempts</small><b>{simulation.attempt_number}/{simulation.max_attempts}</b></div>
            <div><small>No progress</small><b>{simulation.no_progress_detected ? 'Detected' : 'No'}</b></div>
            <div><small>Blocked tools</small><b>{simulation.unauthorized_tool_attempts.length}</b></div>
          </div>
        ) : <div className="loop-simulation-empty">Choose one control test.</div>}
        <div className="boundary-callout loop-principle">
          <strong>Controlled autonomy</strong>
          <span>Trigger → goal → permitted tools → evidence → verification → pass, retry, escalate or stop.</span>
        </div>
      </aside>
    </section>
  )
}
