import { useEffect, useMemo, useState } from 'react'
import { api, downloadJson } from '../api.js'
import StatusBadge from '../components/StatusBadge.jsx'

const statusOptions = [
  ['', 'All statuses'],
  ['auto_cleared', 'Auto cleared'],
  ['awaiting_human_review', 'Awaiting human review'],
  ['blocked', 'Blocked'],
  ['approved', 'Approved'],
  ['rejected', 'Rejected'],
  ['more_information_requested', 'More information requested'],
  ['returned_for_correction', 'Returned for correction'],
]

const routeOptions = [
  ['', 'All routes'],
  ['low_risk', 'Low risk'],
  ['human_review', 'Human review'],
  ['escalated_review', 'Escalated review'],
  ['blocked', 'Blocked'],
  ['returned_for_correction', 'Returned for correction'],
]

export default function CaseLibrary({ refreshToken = 0, onOpenAudit, onOpenProof }) {
  const [cases, setCases] = useState([])
  const [summary, setSummary] = useState(null)
  const [selectedId, setSelectedId] = useState('')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [route, setRoute] = useState('')
  const [busy, setBusy] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')

  const selected = useMemo(
    () => cases.find((item) => item.case_id === selectedId) || cases[0] || null,
    [cases, selectedId],
  )

  const load = async () => {
    setBusy(true)
    setError('')
    try {
      const [records, counts] = await Promise.all([
        api.getCases({ query, status, route, limit: 200 }),
        api.getCaseSummary(),
      ])
      setCases(records)
      setSummary(counts)
      setSelectedId((current) => records.some((item) => item.case_id === current) ? current : records[0]?.case_id || '')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { load() }, [refreshToken])

  const exportSelected = async () => {
    if (!selected) return
    setExporting(true)
    setError('')
    try {
      const evidence = await api.getEvidence(selected.case_id)
      downloadJson(`${selected.case_id}-evidence.json`, evidence)
    } catch (err) {
      setError(err.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <section className="library-layout page-fill">
      <aside className="panel library-list-panel">
        <div className="panel__heading compact-heading">
          <div><p className="eyebrow">Synthetic records</p><h2>Case library</h2></div>
          <button type="button" className="icon-button" onClick={load} disabled={busy} title="Reload case list and summary counts">{busy ? '…' : '↻'}</button>
        </div>

        <form className="library-filters" onSubmit={(event) => { event.preventDefault(); load() }}>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, ID, host or purpose" />
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            {statusOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <select value={route} onChange={(event) => setRoute(event.target.value)}>
            {routeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <button className="secondary">Apply</button>
        </form>

        {error && <div className="error">{error}</div>}
        <div className="library-count-line">
          <span>{cases.length} shown</span>
          <strong>{summary?.total || 0} total</strong>
        </div>
        <div className="library-list panel-scroll">
          {cases.length === 0 ? (
            <div className="empty-state"><strong>No cases found</strong><span>Run a synthetic scenario or clear the filters.</span></div>
          ) : cases.map((record) => (
            <button
              type="button"
              key={record.case_id}
              className={`library-item ${selected?.case_id === record.case_id ? 'active' : ''}`}
              onClick={() => setSelectedId(record.case_id)}
            >
              <div>
                <strong>{record.request.visitor_name}</strong>
                <small>{record.case_id}</small>
              </div>
              <StatusBadge value={record.status} />
              <span>{record.risk.route.replaceAll('_', ' ')} · score {record.risk.score}</span>
              <time>{new Date(record.created_at).toLocaleString([], { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' })}</time>
            </button>
          ))}
        </div>
      </aside>

      <article className="panel library-detail-panel">
        {!selected ? (
          <div className="empty-state empty-state--large"><strong>Select a case</strong><span>Its decision, provenance and evidence controls will appear here.</span></div>
        ) : (
          <>
            <div className="library-detail-header">
              <div><p className="eyebrow">Case record</p><h2>{selected.request.visitor_name}</h2><span>{selected.case_id}</span></div>
              <StatusBadge value={selected.status} />
            </div>

            <div className="library-metrics">
              <div><span>Route</span><strong>{selected.risk.route.replaceAll('_', ' ')}</strong></div>
              <div><span>Score</span><strong>{selected.risk.score}</strong></div>
              <div><span>Security</span><strong>{selected.security?.status || 'not run'}</strong></div>
              <div><span>Policies</span><strong>{selected.policies.map((item) => item.id).join(', ') || 'none'}</strong></div>
            </div>

            <div className="library-detail-grid">
              <div className="case-context-card">
                <span className="section-kicker">Request context</span>
                <dl className="context-list">
                  <div><dt>Type</dt><dd>{selected.request.visitor_type}</dd></div>
                  <div><dt>Host</dt><dd>{selected.request.host_name || 'Not supplied'}</dd></div>
                  <div><dt>Purpose</dt><dd>{selected.request.visit_purpose || 'Not supplied'}</dd></div>
                  <div><dt>Area</dt><dd>{selected.request.requested_area.replaceAll('_', ' ')}</dd></div>
                </dl>
              </div>
              <div className="case-context-card">
                <span className="section-kicker">Review provenance</span>
                <dl className="context-list">
                  <div><dt>Source</dt><dd>{selected.review?.fallback_used ? 'safe fallback' : selected.review?.model_invoked ? 'Gemini via ADK' : 'pre-model control'}</dd></div>
                  <div><dt>Model</dt><dd>{selected.review?.model_name || 'not invoked'}</dd></div>
                  <div><dt>MCP</dt><dd>{selected.review?.tool_calls?.length || 0} successful call(s)</dd></div>
                  <div><dt>Elapsed</dt><dd>{selected.review?.latency_ms || 0} ms</dd></div>
                </dl>
              </div>
            </div>

            <div className="case-summary-card">
              <strong>{selected.review ? 'Bounded review' : 'Security control outcome'}</strong>
              <p>{selected.review?.summary || 'The input was blocked before a model review could run.'}</p>
            </div>

            <div className="library-actions">
              <button className="secondary" onClick={() => onOpenAudit?.(selected.case_id)}>Open audit</button>
              <button className="secondary" onClick={() => onOpenProof?.(selected.case_id)}>Proof & replay</button>
              <button className="primary" onClick={exportSelected} disabled={exporting}>{exporting ? 'Preparing…' : 'Download evidence'}</button>
            </div>
          </>
        )}
      </article>
    </section>
  )
}
