import { useMemo, useState } from 'react'
import { api } from '../api.js'

const manualTests = [
  { id: 'routine', number: '01', title: 'Routine clearance', detail: 'Low risk, policy VP-1.1, Gemini/MCP review, automatic finalisation.' },
  { id: 'review', number: '02', title: 'Human review', detail: 'After-hours restricted access, score 5, reviewer decision and audit finalisation.' },
  { id: 'unsafe', number: '03', title: 'Pre-model security gate', detail: 'Prompt injection blocked before Gemini, score 10 and controlled human action.' },
]

export default function TestLab({ onScenario, onNavigate, onResetComplete }) {
  const [report, setReport] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirmReset, setConfirmReset] = useState(false)
  const [resetBusy, setResetBusy] = useState(false)

  const requiredSummary = useMemo(() => {
    const required = report?.checks?.filter((item) => item.required) || []
    return {
      passed: required.filter((item) => item.status === 'pass').length,
      total: required.length,
    }
  }, [report])

  const runChecks = async () => {
    setBusy(true)
    setReport(null)
    setError('')
    try {
      setReport(await api.runSystemCheck())
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const resetDemo = async () => {
    if (!confirmReset) {
      setConfirmReset(true)
      return
    }
    setResetBusy(true)
    setError('')
    try {
      await api.resetDemo()
      setReport(null)
      setConfirmReset(false)
      onResetComplete?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setResetBusy(false)
    }
  }

  return (
    <section className="testlab-layout page-fill">
      <div className="panel testlab-main">
        <div className="panel__heading compact-heading">
          <div>
            <p className="eyebrow">Feature-by-feature validation</p>
            <h2>Release test lab</h2>
          </div>
          <button className="primary" onClick={runChecks} disabled={busy}>{busy ? 'Checking…' : 'Run automated checks'}</button>
        </div>
        {error && <div className="error">{error}</div>}

        {!report ? (
          <div className={`testlab-ready ${busy ? 'testlab-ready--busy' : ''}`}>
            <div className="testlab-orbit">{busy ? '…' : 'RC'}</div>
            <div>
              <strong>{busy ? 'Verification in progress' : 'Not verified yet'}</strong>
              <span>{busy ? 'Pass and warning states will appear only after the backend finishes the checks.' : 'Run the automated checks first, then validate each scenario using the guided cards below.'}</span>
            </div>
          </div>
        ) : (
          <div className="testlab-report">
            <div className={`testlab-verdict testlab-verdict--${report.overall}`}>
              <strong>{report.overall === 'pass' ? 'Required controls passed' : 'Required control failure'}</strong>
              <span>{requiredSummary.passed}/{requiredSummary.total} required checks · {report.release} · v{report.version}</span>
            </div>
            <div className="check-grid panel-scroll">
              {report.checks.map((check) => (
                <div key={check.id} className={`check-card check-card--${check.status}`}>
                  <span>{check.status === 'pass' ? '✓' : check.status === 'warning' ? '!' : '×'}</span>
                  <div><strong>{check.label}</strong><small>{check.detail}</small></div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="manual-test-row">
          {manualTests.map((test) => (
            <button key={test.id} className="manual-test-card" onClick={() => onScenario?.(test.id)}>
              <span>{test.number}</span>
              <div><strong>{test.title}</strong><small>{test.detail}</small></div>
              <em>Open →</em>
            </button>
          ))}
        </div>
      </div>

      <aside className="panel testlab-side panel-scroll">
        <div>
          <p className="eyebrow">Submission readiness</p>
          <h2>Evidence centre</h2>
        </div>
        <ul className="proof-list testlab-proof-list">
          <li><strong>Public-safe architecture</strong><span>Synthetic data, bounded model authority, read-only MCP and explicit IP boundary.</span></li>
          <li><strong>Reproducible evaluation</strong><span>Thirty deterministic cases plus optional five-case live agent quality check.</span></li>
          <li><strong>Human governance</strong><span>Approve, reject and request-information actions produce final audit evidence.</span></li>
          <li><strong>Proof-carrying decisions</strong><span>Every case can export a SHA-256 proof packet with source confidence, policy tensions and a linked audit chain.</span></li>
          <li><strong>Deterministic replay</strong><span>What-if evidence changes are simulated without rewriting the original record.</span></li>
          <li><strong>Bounded loop engineering</strong><span>Every operational stage records trigger, goal, permitted tools, verification, attempts, decision and stop reason.</span></li>
          <li><strong>Submission assets included</strong><span>Writeup draft, five-minute video script, demo runbook, judging matrix and deployment guide.</span></li>
        </ul>

        <div className="testlab-shortcuts">
          <button onClick={() => onNavigate?.('proof')}>Open proof & replay</button>
          <button onClick={() => onNavigate?.('loops')}>Open loop observatory</button>
          <button onClick={() => onNavigate?.('cases')}>Review case library</button>
          <button onClick={() => onNavigate?.('evaluation')}>Open evaluations</button>
          <button onClick={() => onNavigate?.('audit')}>Inspect audit evidence</button>
        </div>

        <div className="reset-card">
          <strong>Clean-demo control</strong>
          <span>Delete only locally stored synthetic cases and audit events before the official recording.</span>
          <button className={confirmReset ? 'decision-reject' : ''} onClick={resetDemo} disabled={resetBusy}>
            {resetBusy ? 'Resetting…' : confirmReset ? 'Confirm synthetic reset' : 'Reset demo data'}
          </button>
          {confirmReset && <small>Click once more to confirm. Source code and evaluation datasets are unaffected.</small>}
        </div>
      </aside>
    </section>
  )
}
