import { useEffect, useMemo, useState } from 'react'
import { api, downloadJson } from '../api.js'
import StatusBadge from '../components/StatusBadge.jsx'

function shortHash(value = '') {
  return value ? `${value.slice(0, 12)}…${value.slice(-8)}` : 'not generated'
}

function confidenceLabel(value) {
  return `${Math.round((value || 0) * 100)}%`
}

function bestCaseForScenario(cases, scenarioId) {
  if (!cases.length) return null
  if (scenarioId === 'model_outage') {
    return cases.find((item) => item.risk.route === 'escalated_review' && item.review)
      || cases.find((item) => item.risk.route !== 'blocked' && item.review)
      || cases[0]
  }
  return cases.find((item) => item.risk.route === 'low_risk' && item.status === 'auto_cleared')
    || cases.find((item) => item.risk.route !== 'blocked')
    || cases[0]
}

function impactTone(kind = '') {
  if (kind === 'route_change') return 'change'
  if (kind === 'control_preserved') return 'preserved'
  if (kind === 'evidence_change') return 'evidence'
  return 'neutral'
}

export default function ProofLab({ latestCaseId = '', refreshToken = 0, onOpenAudit }) {
  const [cases, setCases] = useState([])
  const [selectedId, setSelectedId] = useState(latestCaseId)
  const [proof, setProof] = useState(null)
  const [scenarios, setScenarios] = useState([])
  const [selectedScenario, setSelectedScenario] = useState('host_confirmation_removed')
  const [replay, setReplay] = useState(null)
  const [portableCheck, setPortableCheck] = useState(null)
  const [tamperCheck, setTamperCheck] = useState(null)
  const [busy, setBusy] = useState(false)
  const [replayBusy, setReplayBusy] = useState(false)
  const [error, setError] = useState('')

  const selected = useMemo(() => cases.find((item) => item.case_id === selectedId) || cases[0] || null, [cases, selectedId])
  const selectedScenarioMeta = useMemo(() => scenarios.find((item) => item.id === selectedScenario), [scenarios, selectedScenario])
  const recommendedCase = useMemo(() => bestCaseForScenario(cases, selectedScenario), [cases, selectedScenario])
  const selectedIsRecommended = Boolean(selected && recommendedCase && selected.case_id === recommendedCase.case_id)

  const loadCases = async () => {
    setError('')
    try {
      const records = await api.getCases({ limit: 100 })
      setCases(records)
      setSelectedId((current) => records.some((item) => item.case_id === current)
        ? current
        : latestCaseId && records.some((item) => item.case_id === latestCaseId)
          ? latestCaseId
          : records[0]?.case_id || '')
    } catch (err) { setError(err.message) }
  }

  const loadProof = async (caseId) => {
    if (!caseId) { setProof(null); return }
    setBusy(true)
    setError('')
    setReplay(null)
    setPortableCheck(null)
    setTamperCheck(null)
    try { setProof(await api.getProof(caseId)) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  useEffect(() => { loadCases() }, [refreshToken])
  useEffect(() => { api.getReplayScenarios().then((payload) => setScenarios(payload.scenarios || [])).catch(() => setScenarios([])) }, [])
  useEffect(() => { if (selected?.case_id) loadProof(selected.case_id) }, [selected?.case_id])

  const chooseScenario = (scenarioId) => {
    setSelectedScenario(scenarioId)
    setReplay(null)
    const best = bestCaseForScenario(cases, scenarioId)
    const current = cases.find((item) => item.case_id === selectedId)
    const recommendedRoute = scenarios.find((item) => item.id === scenarioId)?.recommended_route
    if (best && current && recommendedRoute && current.risk.route !== recommendedRoute) {
      setSelectedId(best.case_id)
    }
  }

  const runReplay = async () => {
    if (!selected || !selectedScenario) return
    setReplayBusy(true)
    setError('')
    try { setReplay(await api.runReplay(selected.case_id, selectedScenario)) } catch (err) { setError(err.message) } finally { setReplayBusy(false) }
  }

  const verifyPortable = async () => {
    if (!proof) return
    setBusy(true)
    setError('')
    try {
      const browserRoundTrip = JSON.parse(JSON.stringify(proof))
      const verification = await api.verifyPortableProof(browserRoundTrip)
      setPortableCheck(verification)
      setProof((current) => current ? { ...current, verification } : current)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const runTamperDemo = async () => {
    if (!selected) return
    setBusy(true)
    setError('')
    try { setTamperCheck(await api.runProofTamperDemo(selected.case_id)) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <section className="proof-layout page-fill">
      <aside className="panel proof-case-panel">
        <div className="panel__heading compact-heading">
          <div><p className="eyebrow">Proof-bearing records</p><h2>Select case</h2></div>
          <button className="icon-button" onClick={loadCases} title="Reload latest proof-bearing case list">↻</button>
        </div>
        {error && <div className="error">{error}</div>}
        <div className="proof-case-list panel-scroll">
          {cases.length === 0 ? (
            <div className="empty-state"><strong>No cases yet</strong><span>Run a synthetic case first.</span></div>
          ) : cases.map((record) => (
            <button key={record.case_id} className={`proof-case-item ${selected?.case_id === record.case_id ? 'active' : ''}`} onClick={() => setSelectedId(record.case_id)}>
              <div><strong>{record.request.visitor_name}</strong><small>{record.case_id}</small></div>
              <StatusBadge value={record.status} />
              <span>{record.risk.route.replaceAll('_', ' ')} · score {record.risk.score}</span>
            </button>
          ))}
        </div>
        {selected && (
          <div className="proof-case-actions">
            <button onClick={() => onOpenAudit?.(selected.case_id)}>Audit</button>
            <button className="primary" disabled={!proof} onClick={() => downloadJson(`${selected.case_id}-proof-packet.json`, proof)}>Download proof</button>
          </div>
        )}
      </aside>

      <article className="panel proof-packet-panel">
        {!proof ? (
          <div className="empty-state empty-state--large"><strong>{busy ? 'Generating proof…' : 'Select a case'}</strong><span>Source confidence, conflict handling and portable integrity evidence will appear here.</span></div>
        ) : (
          <>
            <div className="proof-title-row">
              <div><p className="eyebrow">Decision proof packet</p><h2>{proof.case_id}</h2></div>
              <div className={`proof-seal ${proof.verification?.verified ? 'proof-seal--verified' : ''}`}><span>{proof.verification?.verified ? 'Portable verified' : 'Check'}</span><strong>SHA-256</strong></div>
            </div>
            <div className="proof-hash-grid">
              <div><span>Packet hash</span><strong title={proof.integrity.packet_hash}>{shortHash(proof.integrity.packet_hash)}</strong></div>
              <div><span>Audit root</span><strong title={proof.integrity.audit_root_hash}>{shortHash(proof.integrity.audit_root_hash)}</strong></div>
              <div><span>Chain events</span><strong>{proof.integrity.event_count}</strong></div>
              <div><span>Canonical profile</span><strong>{proof.integrity.canonical_profile || 'GTS-CJ-1'}</strong></div>
            </div>

            <div className="portable-proof-bar">
              <div>
                <strong>Export-safe integrity</strong>
                <span>Browser JSON round-trip verification · unsigned tamper-evident packet</span>
              </div>
              <div className="portable-proof-actions">
                <button onClick={verifyPortable} disabled={busy}>{busy ? 'Checking…' : 'Verify exported form'}</button>
                <button onClick={runTamperDemo} disabled={busy}>Tamper test</button>
              </div>
            </div>

            {(portableCheck || tamperCheck) && (
              <div className="proof-check-strip">
                {portableCheck && <span className={portableCheck.verified ? 'pass' : 'fail'}>{portableCheck.verified ? '✓ Round-trip PASS' : `! ${portableCheck.failed_checks?.join(', ') || 'Verification failed'}`}</span>}
                {tamperCheck && <span className={tamperCheck.detected ? 'pass' : 'fail'}>{tamperCheck.detected ? '✓ Tampering detected' : '! Tamper test failed'}</span>}
              </div>
            )}

            {proof.loop_control_map && (
              <div className="proof-loop-bar">
                <div><span>Bounded loops</span><strong>{proof.loop_control_map.bounded_runs}/{proof.loop_control_map.total_runs}</strong></div>
                <div><span>Retries</span><strong>{proof.loop_control_map.total_retries}</strong></div>
                <div><span>Blocked tools</span><strong>{proof.loop_control_map.unauthorized_tool_attempts}</strong></div>
                <div><span>No-progress stops</span><strong>{proof.loop_control_map.no_progress_stops}</strong></div>
              </div>
            )}

            <div className="proof-section-heading"><strong>Source confidence map</strong><span>{proof.policy_conflict_map.overall.replaceAll('_', ' ')}</span></div>
            <div className="source-map panel-scroll">
              {proof.source_confidence_map.map((source) => (
                <div key={source.source_id} className={`source-row source-row--${source.class}`}>
                  <div className="source-row__head"><strong>{source.label}</strong><span>{confidenceLabel(source.confidence)}</span></div>
                  <div className="confidence-track"><i style={{ width: confidenceLabel(source.confidence) }} /></div>
                  <small>{source.authority} · {source.status}</small>
                </div>
              ))}
            </div>
            <div className="conflict-summary">
              <div><strong>Policy conflict map</strong><span>{proof.policy_conflict_map.count} exposed tension(s)</span></div>
              {proof.policy_conflict_map.tensions.length ? (
                <ul>{proof.policy_conflict_map.tensions.map((item) => <li key={`${item.signal}-${item.policy}`}><strong>{item.signal.replaceAll('_', ' ')}</strong><span>{item.policy} · {item.resolution}</span></li>)}</ul>
              ) : <p>No unresolved policy tension. Evidence is aligned.</p>}
            </div>
          </>
        )}
      </article>

      <aside className="panel replay-panel">
        <div><p className="eyebrow">Replay laboratory</p><h2>What-if proof</h2></div>
        <p className="replay-intro">Change evidence without altering the original record. Smart selection avoids visually redundant demos.</p>

        {recommendedCase && (
          <div className={`replay-recommendation ${selectedIsRecommended ? 'active' : ''}`}>
            <div><span>Recommended case</span><strong>{recommendedCase.request.visitor_name} · {recommendedCase.risk.route.replaceAll('_', ' ')}</strong></div>
            {!selectedIsRecommended && <button onClick={() => setSelectedId(recommendedCase.case_id)}>Use case</button>}
          </div>
        )}

        <div className="replay-scenarios panel-scroll">
          {scenarios.map((scenario) => (
            <button key={scenario.id} className={selectedScenario === scenario.id ? 'active' : ''} onClick={() => chooseScenario(scenario.id)}>
              <strong>{scenario.label}</strong><small>{scenario.description}</small><em>{scenario.expected_effect}</em>
            </button>
          ))}
        </div>
        <button className="primary replay-run" onClick={runReplay} disabled={!selected || replayBusy}>{replayBusy ? 'Replaying…' : 'Run deterministic replay'}</button>
        {replay ? (
          <div className={`replay-result replay-result--${impactTone(replay.impact?.kind)}`}>
            <div className="replay-impact-label">{replay.impact?.label || 'Replay complete'}</div>
            <div className="replay-compare">
              <div><span>Original</span><strong>{replay.original.route.replaceAll('_', ' ')}</strong><small>score {replay.original.score}</small></div>
              <b>→</b>
              <div><span>Simulated</span><strong>{replay.simulated.route.replaceAll('_', ' ')}</strong><small>score {replay.simulated.score}</small></div>
            </div>
            <div className="replay-delta"><span>Score delta</span><strong>{replay.delta.score_delta > 0 ? '+' : ''}{replay.delta.score_delta}</strong></div>
            <div className="replay-tags">{replay.simulated.policy_ids.map((id) => <span key={id}>{id}</span>)}</div>
            <p>{replay.proof_statement}</p>
          </div>
        ) : <div className="replay-empty">Select a scenario and run the replay.</div>}
      </aside>
    </section>
  )
}
