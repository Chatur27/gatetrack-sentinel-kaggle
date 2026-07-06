import { useEffect, useMemo, useState } from 'react'
import VisitorForm from './pages/VisitorForm.jsx'
import ReviewQueue from './pages/ReviewQueue.jsx'
import CaseLibrary from './pages/CaseLibrary.jsx'
import AuditViewer from './pages/AuditViewer.jsx'
import Evaluation from './pages/Evaluation.jsx'
import TestLab from './pages/TestLab.jsx'
import ProofLab from './pages/ProofLab.jsx'
import LoopControl from './pages/LoopControl.jsx'
import { api } from './api.js'
import { APP_VERSION, RELEASE_LABEL } from './release.js'
import brandMark from './assets/gatetrack-sentinel-mark.svg'

const tabs = [
  ['intake', 'Visitor request', '01'],
  ['reviews', 'Review queue', '02'],
  ['cases', 'Case library', '03'],
  ['audit', 'Audit viewer', '04'],
  ['evaluation', 'Evaluation', '05'],
  ['proof', 'Proof & replay', '06'],
  ['loops', 'Loop control', '07'],
  ['testlab', 'Test lab', '08'],
]

const pageMeta = {
  intake: {
    eyebrow: 'Operational intake',
    title: 'Visitor risk triage',
    description: 'Validate, secure, route and ground each synthetic visitor request.',
  },
  reviews: {
    eyebrow: 'Human authority',
    title: 'Decision workspace',
    description: 'Resolve elevated and blocked cases with a documented human decision.',
  },
  cases: {
    eyebrow: 'Operational records',
    title: 'Case library',
    description: 'Search synthetic cases, inspect provenance and export evidence packs.',
  },
  audit: {
    eyebrow: 'Evidence trail',
    title: 'Audit timeline',
    description: 'Inspect every deterministic, policy, model and human workflow event.',
  },
  evaluation: {
    eyebrow: 'Reproducibility',
    title: 'Control evaluation',
    description: 'Compare deterministic controls with the optional five-case live agent quality check.',
  },
  proof: {
    eyebrow: 'Proof-carrying operations',
    title: 'Decision proof studio',
    description: 'Verify source confidence, expose policy tensions and replay evidence changes without altering the original case.',
  },
  loops: {
    eyebrow: 'Loop engineering',
    title: 'Bounded execution observatory',
    description: 'Inspect triggers, goals, permitted tools, verification, retries, escalation and terminal states.',
  },
  testlab: {
    eyebrow: 'Release candidate',
    title: 'Feature test lab',
    description: 'Validate the complete concept feature by feature before publication and recording.',
  },
}

export default function App() {
  const [tab, setTab] = useState('intake')
  const [latestCaseId, setLatestCaseId] = useState('')
  const [refreshToken, setRefreshToken] = useState(0)
  const [auditRefreshToken, setAuditRefreshToken] = useState(0)
  const [toast, setToast] = useState(null)
  const [health, setHealth] = useState(null)
  const [healthState, setHealthState] = useState('loading')
  const [scenarioRequest, setScenarioRequest] = useState({ key: '', token: 0 })
  const [aboutOpen, setAboutOpen] = useState(false)

  const meta = useMemo(() => pageMeta[tab], [tab])

  const refreshHealth = async () => {
    setHealthState('loading')
    try {
      const payload = await api.health()
      setHealth(payload)
      setHealthState('online')
    } catch {
      setHealth(null)
      setHealthState('offline')
    }
  }

  useEffect(() => {
    refreshHealth()
    const timer = window.setInterval(refreshHealth, 5000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!toast) return undefined
    const timer = window.setTimeout(() => setToast(null), 4200)
    return () => window.clearTimeout(timer)
  }, [toast])

  const created = (caseId) => {
    setLatestCaseId(caseId)
    setRefreshToken((value) => value + 1)
    setAuditRefreshToken((value) => value + 1)
    window.setTimeout(refreshHealth, 250)
  }

  const decisionRecorded = ({ caseId, action }) => {
    setLatestCaseId(caseId)
    setRefreshToken((value) => value + 1)
    setAuditRefreshToken((value) => value + 1)
    setToast({
      tone: action === 'reject' ? 'danger' : action === 'approve' ? 'success' : 'warning',
      message: `Human decision recorded: ${action.replace('-', ' ')}. Audit evidence refreshed.`,
    })
    setTab('audit')
  }

  const openAudit = (caseId) => {
    setLatestCaseId(caseId)
    setAuditRefreshToken((value) => value + 1)
    setTab('audit')
  }

  const openScenario = (key) => {
    setScenarioRequest({ key, token: Date.now() })
    setTab('intake')
    setToast({ tone: 'success', message: `${key[0].toUpperCase()}${key.slice(1)} scenario loaded for testing.` })
  }

  const resetComplete = () => {
    setLatestCaseId('')
    setRefreshToken((value) => value + 1)
    setAuditRefreshToken((value) => value + 1)
    setToast({ tone: 'warning', message: 'Synthetic cases and audit events were reset.' })
  }

  const live = Boolean(health?.agent?.live_model_available)
  const circuitOpen = Boolean(health?.agent?.circuit_open)
  const circuitReason = health?.agent?.circuit_reason || health?.agent?.live_model_unavailable_reason || ''
  const adkConfigured = Boolean(health?.agent?.configured || health?.model_mode === 'adk')
  const providerLabel = healthState === 'loading'
    ? 'Checking runtime…'
    : healthState === 'offline'
      ? 'Backend offline'
      : circuitOpen
        ? circuitReason.includes('quota')
          ? 'Safe fallback · quota unavailable'
          : 'Safe fallback · live circuit open'
        : live
          ? 'Gemini live'
          : adkConfigured
            ? 'ADK configured · fallback ready'
            : 'Deterministic demo'
  const runtimeTone = healthState === 'offline' ? 'offline' : live ? 'agent' : healthState === 'online' ? 'fallback' : 'checking'
  const displayedRelease = health?.release || RELEASE_LABEL
  const displayedVersion = health?.version || APP_VERSION

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-mark" aria-hidden="true"><img src={brandMark} alt="" /></div>
        <div className="brand-copy">
          <strong>GateTrack Sentinel</strong>
          <span>AUREX Sentinel Labs · Kaggle Capstone Edition</span>
        </div>
        <div className="version-pill">{displayedRelease} · v{displayedVersion}</div>
        <button type="button" className="topbar-status" onClick={refreshHealth}>
          <span className={`live-dot live-dot--${runtimeTone}`} />
          {providerLabel}
        </button>
        <button type="button" className="about-trigger" onClick={() => setAboutOpen(true)}>About</button>
        <div className="demo-pill">Synthetic data only</div>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <div className="sidebar-intro">
            <p className="eyebrow">Human-governed workflow</p>
            <strong>Proof attached.<br />Loops bounded.<br />Authority preserved.</strong>
          </div>

          <nav className="side-nav" aria-label="Application sections">
            {tabs.map(([key, label, number]) => (
              <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>
                <span>{number}</span>
                <strong>{label}</strong>
              </button>
            ))}
          </nav>

          <div className="sidebar-note">
            <strong>Educational demonstration</strong>
            <span>No legal, regulatory, security, immigration, sanctions or compliance decisions.</span>
          </div>
        </aside>

        <section className="workspace">
          <header className="workspace-header">
            <div>
              <p className="eyebrow">{meta.eyebrow}</p>
              <h1>{meta.title}</h1>
            </div>
            <p>{meta.description}</p>
            {latestCaseId && <button className="case-chip" onClick={() => openAudit(latestCaseId)}>Latest: {latestCaseId}</button>}
          </header>

          <main className="workspace-content">
            {tab === 'intake' && (
              <VisitorForm
                onCaseCreated={created}
                requestedScenario={scenarioRequest.key}
                scenarioToken={scenarioRequest.token}
              />
            )}
            {tab === 'reviews' && <ReviewQueue refreshToken={refreshToken} onDecision={decisionRecorded} />}
            {tab === 'cases' && <CaseLibrary refreshToken={refreshToken} onOpenAudit={openAudit} onOpenProof={(caseId) => { setLatestCaseId(caseId); setTab('proof') }} />}
            {tab === 'audit' && <AuditViewer latestCaseId={latestCaseId} refreshToken={auditRefreshToken} />}
            {tab === 'evaluation' && <Evaluation onRuntimeRefresh={refreshHealth} />}
            {tab === 'proof' && <ProofLab latestCaseId={latestCaseId} refreshToken={refreshToken} onOpenAudit={openAudit} />}
            {tab === 'loops' && <LoopControl latestCaseId={latestCaseId} refreshToken={refreshToken} />}
            {tab === 'testlab' && (
              <TestLab
                onScenario={openScenario}
                onNavigate={setTab}
                onResetComplete={resetComplete}
              />
            )}
          </main>
        </section>
      </div>

      {aboutOpen && (
        <div className="modal-backdrop about-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setAboutOpen(false) }}>
          <section className="about-modal" role="dialog" aria-modal="true" aria-labelledby="about-title">
            <div className="about-modal__header">
              <div className="about-logo-row">
                <img src={brandMark} alt="GateTrack Sentinel logo mark" />
                <div>
                  <p className="eyebrow">AUREX Sentinel Labs</p>
                  <h2 id="about-title">About GateTrack Sentinel</h2>
                </div>
              </div>
              <button type="button" className="modal-close" onClick={() => setAboutOpen(false)} aria-label="Close about panel">×</button>
            </div>
            <p>
              GateTrack Sentinel is a human-governed AI control prototype for synthetic visitor-risk triage,
              bounded review, audit evidence and proof-carrying decisions.
            </p>
            <div className="about-builders">
              <div><span>Lead Developer / Co-Founder</span><strong>Chaturparsad Baijnath</strong></div>
              <div><span>Co-Developer / Founder</span><strong>Sarasvadee Kistnen Baijnath</strong></div>
            </div>
            <p className="about-note">
              Built as a founder-led exploration of practical, auditable and human-supervised AI systems for operational risk,
              compliance support and responsible decision workflows. Synthetic educational demonstration only.
            </p>
          </section>
        </div>
      )}
      {toast && <div className={`toast toast--${toast.tone}`} role="status">{toast.message}</div>}
    </div>
  )
}
