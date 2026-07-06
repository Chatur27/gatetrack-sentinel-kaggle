import { useEffect, useMemo, useState } from 'react'
import { api, downloadJson } from '../api.js'

const eventNames = {
  intake_received: 'Intake received',
  validation_completed: 'Validation completed',
  security_completed: 'Security completed',
  routing_completed: 'Routing completed',
  policy_retrieved: 'Policy retrieved',
  review_generated: 'Review generated',
  model_skipped: 'Model skipped',
  human_review_required: 'Human review required',
  human_decision_recorded: 'Human decision recorded',
  initial_workflow_completed: 'Initial workflow completed',
  case_completed: 'Initial workflow completed',
  case_finalised: 'Case finalised',
  case_status_updated: 'Case status updated',
}

export default function AuditViewer({ latestCaseId, refreshToken = 0 }) {
  const [caseId, setCaseId] = useState(latestCaseId || '')
  const [events, setEvents] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [exporting, setExporting] = useState(false)

  const newestFirst = useMemo(() => [...events].reverse(), [events])
  const selected = useMemo(
    () => events.find((item) => item.event_id === selectedId) || newestFirst[0] || null,
    [events, newestFirst, selectedId],
  )

  const loadCase = async (id) => {
    const cleanId = id.trim()
    if (!cleanId) return
    setBusy(true)
    setError('')
    try {
      const result = await api.getAudit(cleanId)
      setCaseId(cleanId)
      setEvents(result.events)
      setSelectedId(result.events.at(-1)?.event_id || '')
    } catch (err) {
      setEvents([])
      setSelectedId('')
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const load = (event) => {
    event.preventDefault()
    loadCase(caseId)
  }

  useEffect(() => {
    if (latestCaseId) loadCase(latestCaseId)
  }, [latestCaseId, refreshToken])

  const exportEvidence = async () => {
    const cleanId = caseId.trim()
    if (!cleanId) return
    setExporting(true)
    setError('')
    try {
      const payload = await api.getEvidence(cleanId)
      downloadJson(`${cleanId}-evidence.json`, payload)
    } catch (err) {
      setError(err.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <section className="audit-page page-fill">
      <div className="panel audit-toolbar">
        <form className="audit-search" onSubmit={load}>
          <div>
            <p className="eyebrow">Case evidence</p>
            <h2>Audit explorer</h2>
          </div>
          <input value={caseId} onChange={(event) => setCaseId(event.target.value)} placeholder="GTS-YYYYMMDD-XXXXXX" />
          <div className="audit-toolbar-actions">
            <button type="button" onClick={exportEvidence} disabled={exporting || !caseId.trim()}>{exporting ? 'Exporting…' : 'Export'}</button>
            <button className="primary" disabled={busy}>{busy ? 'Loading…' : 'Load case'}</button>
          </div>
        </form>
        {error && <div className="error">{error}</div>}
      </div>

      <div className="audit-layout">
        <aside className="panel event-rail">
          <div className="event-rail__heading"><span>Newest first</span><strong>{events.length} events</strong></div>
          <div className="event-list panel-scroll">
            {newestFirst.length === 0 ? (
              <div className="empty-state"><strong>No timeline loaded</strong><span>Enter a case ID or use the latest case chip.</span></div>
            ) : newestFirst.map((item, index) => (
              <button
                type="button"
                key={item.event_id}
                className={`event-item ${selected?.event_id === item.event_id ? 'active' : ''}`}
                onClick={() => setSelectedId(item.event_id)}
              >
                <span className={`event-dot event-dot--${item.event_type}`} />
                <div><strong>{eventNames[item.event_type] || item.event_type.replaceAll('_', ' ')}</strong><small>{item.node}</small></div>
                <time>{new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time>
                {index === 0 && <em>Latest</em>}
              </button>
            ))}
          </div>
        </aside>

        <article className="panel event-detail">
          {!selected ? (
            <div className="empty-state empty-state--large"><strong>Select an event</strong><span>Structured audit evidence will appear here.</span></div>
          ) : (
            <>
              <div className="event-detail__header">
                <div><p className="eyebrow">{selected.node}</p><h2>{eventNames[selected.event_type] || selected.event_type.replaceAll('_', ' ')}</h2></div>
                <time>{new Date(selected.timestamp).toLocaleString()}</time>
              </div>
              <p className="event-message">{selected.message}</p>
              <div className="event-meta-grid">
                <div><span>Case</span><strong>{selected.case_id}</strong></div>
                <div><span>Event ID</span><strong>{selected.event_id.slice(0, 18)}…</strong></div>
              </div>
              <div className="json-card panel-scroll">
                <div className="json-card__title"><span>Structured details</span><small>JSON evidence</small></div>
                <pre>{JSON.stringify(selected.details, null, 2)}</pre>
              </div>
            </>
          )}
        </article>
      </div>
    </section>
  )
}
