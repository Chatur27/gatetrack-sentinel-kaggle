import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import StatusBadge from '../components/StatusBadge.jsx'

const initialReviewer = 'Demo Supervisor'

const actionCopy = {
  approve: { title: 'Approve case', button: 'Confirm approval', tone: 'approve' },
  reject: { title: 'Reject case', button: 'Confirm rejection', tone: 'reject' },
  'request-info': { title: 'Request more information', button: 'Send information request', tone: 'request' },
}

export default function ReviewQueue({ refreshToken = 0, onDecision }) {
  const [cases, setCases] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [modal, setModal] = useState(null)
  const [reviewer, setReviewer] = useState(initialReviewer)
  const [reason, setReason] = useState('')

  const selected = useMemo(
    () => cases.find((record) => record.case_id === selectedId) || cases[0] || null,
    [cases, selectedId],
  )

  const load = async () => {
    setBusy(true)
    setError('')
    try {
      const result = await api.getReviews()
      setCases(result)
      setSelectedId((current) => result.some((item) => item.case_id === current) ? current : result[0]?.case_id || '')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { load() }, [refreshToken])

  const openDecision = (record, action) => {
    setReviewer(initialReviewer)
    setReason('')
    setError('')
    setModal({ record, action })
  }

  const closeDecision = () => {
    if (busy) return
    setModal(null)
    setReviewer(initialReviewer)
    setReason('')
    setError('')
  }

  const submitDecision = async (event) => {
    event.preventDefault()
    if (!modal || !reviewer.trim() || !reason.trim()) return
    setBusy(true)
    setError('')
    try {
      const updated = await api.decide(modal.record.case_id, modal.action, {
        reviewer: reviewer.trim(),
        reason: reason.trim(),
      })
      const caseId = modal.record.case_id
      const action = modal.action
      setModal(null)
      setReviewer(initialReviewer)
      setReason('')
      setError('')
      await load()
      onDecision?.({ caseId, action, record: updated })
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <section className="review-layout page-fill">
      <aside className="panel queue-panel">
        <div className="panel__heading compact-heading">
          <div><p className="eyebrow">Pending authority</p><h2>Queue</h2></div>
          <button type="button" className="icon-button" onClick={load} disabled={busy} title="Reload latest pending review cases">{busy ? '…' : '↻'}</button>
        </div>
        {error && !modal && <div className="error">{error}</div>}
        <div className="queue-list panel-scroll">
          {cases.length === 0 ? (
            <div className="empty-state"><strong>Queue clear</strong><span>No cases currently require human action.</span></div>
          ) : cases.map((record) => (
            <button
              type="button"
              key={record.case_id}
              className={`queue-item ${selected?.case_id === record.case_id ? 'active' : ''}`}
              onClick={() => setSelectedId(record.case_id)}
            >
              <div><strong>{record.request.visitor_name}</strong><small>{record.case_id}</small></div>
              <StatusBadge value={record.status} />
              <span>{record.risk.route.replaceAll('_', ' ')} · score {record.risk.score}</span>
            </button>
          ))}
        </div>
      </aside>

      <section className="panel review-detail">
        {!selected ? (
          <div className="empty-state empty-state--large"><strong>No pending decision</strong><span>New reviewable or blocked cases will appear here.</span></div>
        ) : (
          <>
            <div className="review-detail__header">
              <div>
                <p className="eyebrow">Selected case</p>
                <h2>{selected.request.visitor_name}</h2>
                <span>{selected.case_id}</span>
              </div>
              <StatusBadge value={selected.status} />
            </div>

            <div className="review-summary-grid">
              <div><span>Route</span><strong>{selected.risk.route.replaceAll('_', ' ')}</strong></div>
              <div><span>Score</span><strong>{selected.risk.score}</strong></div>
              <div><span>Policy</span><strong>{selected.policies?.map((item) => item.id).join(', ') || 'none'}</strong></div>
              <div><span>Area</span><strong>{selected.request.requested_area.replaceAll('_', ' ')}</strong></div>
            </div>

            <div className={`decision-brief ${selected.status === 'blocked' ? 'decision-brief--blocked' : ''}`}>
              <strong>{selected.status === 'blocked' ? 'Security control outcome' : 'Bounded recommendation'}</strong>
              <p>{selected.review?.summary || 'Security control blocked the input before model review.'}</p>
            </div>

            <div className="detail-columns">
              <div>
                <span className="section-kicker">Triggered factors</span>
                <ul className="factor-list compact-factors">
                  {selected.risk.factors.map((factor) => (
                    <li key={factor.code}><span>{factor.code.replaceAll('_', ' ')}</span><strong>+{factor.points}</strong></li>
                  ))}
                </ul>
              </div>
              <div>
                <span className="section-kicker">Request context</span>
                <dl className="context-list">
                  <div><dt>Type</dt><dd>{selected.request.visitor_type}</dd></div>
                  <div><dt>Host</dt><dd>{selected.request.host_name || 'not provided'}</dd></div>
                  <div><dt>Purpose</dt><dd>{selected.request.visit_purpose || 'not provided'}</dd></div>
                </dl>
              </div>
            </div>

            <div className="actions decision-actions">
              {selected.status !== 'blocked' && <button className="approve" onClick={() => openDecision(selected, 'approve')}>Approve</button>}
              <button className="reject" onClick={() => openDecision(selected, 'reject')}>Reject</button>
              <button onClick={() => openDecision(selected, 'request-info')}>Request info</button>
            </div>
          </>
        )}
      </section>

      {modal && (
        <div className="modal-backdrop" role="presentation" onMouseDown={closeDecision}>
          <form className="decision-modal" onSubmit={submitDecision} onMouseDown={(event) => event.stopPropagation()}>
            <div className="decision-modal__header">
              <div><p className="eyebrow">Human authority</p><h3>{actionCopy[modal.action].title}</h3></div>
              <button type="button" className="modal-close" onClick={closeDecision}>×</button>
            </div>
            <div className="decision-case-line"><strong>{modal.record.request.visitor_name}</strong><span>{modal.record.case_id}</span></div>
            <label>Reviewer name<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} required /></label>
            <label>Decision reason<textarea value={reason} onChange={(event) => setReason(event.target.value)} rows="4" required placeholder="State the evidence-based reason for this decision…" /></label>
            {error && <div className="error">{error}</div>}
            <div className="modal-actions">
              <button type="button" onClick={closeDecision}>Cancel</button>
              <button className={`primary decision-${actionCopy[modal.action].tone}`} disabled={busy || !reason.trim() || !reviewer.trim()}>
                {busy ? 'Recording…' : actionCopy[modal.action].button}
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  )
}
