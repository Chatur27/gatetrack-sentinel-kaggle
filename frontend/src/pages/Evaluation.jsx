import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'

function percent(value = 0) {
  return `${Math.round(value * 100)}%`
}

function titleCase(value = '') {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export default function Evaluation({ onRuntimeRefresh }) {
  const [report, setReport] = useState(null)
  const [agentReport, setAgentReport] = useState(null)
  const [health, setHealth] = useState(null)
  const [healthState, setHealthState] = useState('loading')
  const [loopSummary, setLoopSummary] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [agentBusy, setAgentBusy] = useState(false)

  useEffect(() => {
    let active = true
    Promise.all([api.health(), api.getLoopSummary()])
      .then(([healthPayload, loopPayload]) => {
        if (!active) return
        setHealth(healthPayload)
        setLoopSummary(loopPayload)
        setHealthState('online')
      })
      .catch((err) => {
        if (!active) return
        setError(err.message)
        setHealthState('offline')
      })
    return () => { active = false }
  }, [])

  const run = async () => {
    setBusy(true)
    setReport(null)
    setError('')
    try {
      setReport(await api.runEvaluation())
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const refreshLocalHealth = async () => {
    try {
      const [healthPayload, loopPayload] = await Promise.all([api.health(), api.getLoopSummary()])
      setHealth(healthPayload)
      setLoopSummary(loopPayload)
      setHealthState('online')
      if (onRuntimeRefresh) onRuntimeRefresh()
    } catch (err) {
      setHealthState('offline')
      setError(err.message)
    }
  }

  const runAgent = async () => {
    setAgentBusy(true)
    setAgentReport(null)
    setError('')
    try {
      const result = await api.runAgentEvaluation()
      setAgentReport(result)
      await refreshLocalHealth()
    } catch (err) {
      setError(err.message)
      await refreshLocalHealth()
    } finally {
      setAgentBusy(false)
    }
  }

  const s = report?.summary
  const metrics = s ? [
    ['Routing', `${Math.round(s.correct_routing_rate * 100)}%`, '30 deterministic routes'],
    ['Policy match', `${Math.round(s.policy_match_rate * 100)}%`, 'Grounding reference accuracy'],
    ['Security detection', `${Math.round(s.security_detection_rate * 100)}%`, 'Defined attacks blocked'],
    ['High-risk recall', `${Math.round(s.high_risk_recall * 100)}%`, 'Escalations retained'],
    ['Audit completeness', `${Math.round(s.audit_completeness_rate * 100)}%`, 'Required evidence present'],
    ['Known leakage', `${s.known_sensitive_data_leakage_count}`, 'Sensitive-data findings'],
  ] : []

  const a = agentReport?.summary
  const agentReady = Boolean(health?.agent?.live_model_available)
  const circuitOpen = Boolean(health?.agent?.circuit_open)
  const circuitReason = health?.agent?.circuit_reason || health?.agent?.live_model_unavailable_reason || ''
  const resilience = agentReport?.resilience_checks || []
  const fallbackText = useMemo(() => {
    const entries = Object.entries(a?.fallback_breakdown || {})
    if (!entries.length) return 'No unexpected fallback reason recorded.'
    return entries.map(([reason, count]) => `${titleCase(reason)} ${count}`).join(' · ')
  }, [a])

  const liveStatus = a
    ? (a.live_success_count > 0 ? (a.health_status || 'partial') : 'unavailable')
    : (agentReport && !agentReport.available ? 'unavailable' : null)
      || (healthState === 'loading' ? 'checking' : healthState === 'offline' ? 'offline' : agentReady ? 'configured' : 'fallback')

  const liveConfigText = healthState === 'loading'
    ? 'Checking runtime readiness…'
    : healthState === 'offline'
      ? 'Backend health could not be reached.'
      : circuitOpen
        ? circuitReason.includes('quota')
          ? 'Gemini quota circuit is open; deterministic fallback remains operational.'
          : 'Live-agent circuit is open; deterministic fallback remains operational.'
        : agentReady
          ? 'Five diverse model-eligible cases'
          : 'Live calls are unavailable; deterministic fallback remains operational.'

  return (
    <section className="evaluation-layout page-fill">
      <div className="panel evaluation-main">
        <div className="panel__heading compact-heading">
          <div><p className="eyebrow">Deterministic baseline</p><h2>30-case control evaluation</h2></div>
          <button className="primary" onClick={run} disabled={busy}>{busy ? 'Running…' : 'Run 30 cases'}</button>
        </div>
        {error && <div className="error">{error}</div>}
        {!s ? (
          <div className={`evaluation-ready ${busy ? 'evaluation-ready--busy' : ''}`}>
            <div className="evaluation-orbit">{busy ? '…' : '30'}</div>
            <div>
              <strong>{busy ? 'Evaluation in progress' : 'Not run yet'}</strong>
              <span>{busy ? 'Metrics will appear only after the backend completes all cases.' : 'Run the baseline to measure routing, policy matching, security detection, high-risk recall, audit completeness and known leakage.'}</span>
            </div>
          </div>
        ) : (
          <div className="evaluation-grid">
            {metrics.map(([label, value, detail]) => (
              <div key={label}><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>
            ))}
          </div>
        )}
        {loopSummary && (
          <div className="loop-eval-strip">
            <div><span>Bounded loop runs</span><strong>{loopSummary.bounded_runs}/{loopSummary.total_runs}</strong></div>
            <div><span>Recorded retries</span><strong>{loopSummary.total_retries}</strong></div>
            <div><span>Unauthorised execution</span><strong>{loopSummary.unauthorized_tool_attempts}</strong></div>
            <div><span>No-progress stops</span><strong>{loopSummary.no_progress_stops}</strong></div>
          </div>
        )}
      </div>

      <aside className="panel evaluation-notes agent-evaluation-panel panel-scroll">
        <div className="agent-eval-heading">
          <div>
            <p className="eyebrow">Live-agent reliability</p>
            <h2>ADK · MCP · Gemini</h2>
          </div>
          <span className={`readiness-pill readiness-pill--${liveStatus} ${agentReady ? 'readiness-pill--live' : ''}`}>
            {titleCase(liveStatus)}
          </span>
        </div>

        <div className="agent-config-line">
          <span>{health?.agent?.model || health?.model_name || 'gemini-2.5-flash'}</span>
          <strong>{liveConfigText}</strong>
        </div>

        <button className="secondary agent-run-button" onClick={runAgent} disabled={agentBusy || healthState === 'loading'}>
          {agentBusy ? 'Running live reliability check…' : agentReady ? 'Test 5 live-eligible cases' : circuitOpen ? 'Recheck live-agent circuit' : 'Check live-agent availability'}
        </button>

        {agentReport && !agentReport.available && (
          <div className="boundary-callout"><strong>Live check unavailable</strong><span>{agentReport.message}</span></div>
        )}

        {a ? (
          <>
            <div className="agent-metric-grid agent-metric-grid--honest">
              <div className={a.live_success_rate === 1 ? 'metric-pass' : 'metric-warning'}>
                <span>Live success</span><strong>{a.live_success_count}/{a.live_eligible_cases}</strong><small>{percent(a.live_success_rate)} of eligible</small>
              </div>
              <div className={a.mcp_usage_among_live_success_rate === 1 ? 'metric-pass' : 'metric-warning'}>
                <span>MCP on live success</span><strong>{percent(a.mcp_usage_among_live_success_rate)}</strong><small>Successful calls only</small>
              </div>
              <div className={a.unexpected_fallback_rate === 0 ? 'metric-pass' : 'metric-danger'}>
                <span>Unexpected fallback</span><strong>{percent(a.unexpected_fallback_rate)}</strong><small>{a.unexpected_fallback_count} eligible case(s)</small>
              </div>
              <div><span>Route guardrail</span><strong>{percent(a.route_consistency_rate)}</strong><small>Rules remain authoritative</small></div>
              <div><span>Grounding validity</span><strong>{percent(a.grounding_accuracy_rate)}</strong><small>Expected policy retained</small></div>
              <div><span>Live latency</span><strong>{a.average_live_success_latency_ms || 0} ms</strong><small>Successful live calls</small></div>
            </div>

            <div className="agent-diagnostics">
              <div><strong>Fallback breakdown</strong><span>{fallbackText}</span></div>
              <div><strong>Resilience lane</strong><span>{resilience.length ? `${resilience.filter((item) => item.status === 'pass').length}/${resilience.length} passed` : 'Not run'}</span></div>
            </div>

            {resilience.length > 0 && (
              <div className="resilience-strip">
                {resilience.map((item) => (
                  <div key={item.id} className={`resilience-item resilience-item--${item.status}`}>
                    <span>{item.status === 'pass' ? '✓' : '!'}</span><strong>{item.label}</strong>
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <ul className="proof-list proof-list--compact">
            <li><strong>No live score before execution</strong><span>This panel remains explicitly unverified until the backend runs or reports that live mode is unavailable.</span></li>
            <li><strong>Honest denominator</strong><span>Intentional security bypass and outage recovery are not counted as live-agent failures.</span></li>
            <li><strong>Separate resilience lane</strong><span>Security bypass and model-outage route preservation are reported independently.</span></li>
          </ul>
        )}

        <div className="boundary-callout agent-boundary">
          <strong>How to read this panel</strong>
          <span>{a?.interpretation || 'Fallback among model-eligible cases is reported as a real reliability failure, not hidden inside a safety score.'}</span>
        </div>
      </aside>
    </section>
  )
}
