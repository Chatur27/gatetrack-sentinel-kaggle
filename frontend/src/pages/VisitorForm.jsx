import { useEffect, useState } from 'react'
import { api } from '../api.js'
import ResultCard from '../components/ResultCard.jsx'
import { samples } from '../samples.js'

const initial = { ...samples.routine }

export default function VisitorForm({ onCaseCreated, requestedScenario, scenarioToken = 0 }) {
  const [form, setForm] = useState(initial)
  const [record, setRecord] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (requestedScenario && samples[requestedScenario]) {
      setForm({ ...samples[requestedScenario] })
      setRecord(null)
      setError('')
    }
  }, [requestedScenario, scenarioToken])

  const update = (event) => {
    const { name, value, type, checked } = event.target
    setForm((current) => ({
      ...current,
      [name]: type === 'checkbox' ? checked : type === 'number' ? Number(value) : value,
    }))
  }

  const loadSample = (key) => {
    setForm({ ...samples[key] })
    setRecord(null)
    setError('')
  }

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await api.createCase(form)
      setRecord(result)
      onCaseCreated?.(result.case_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="intake-layout page-fill">
      <section className="panel intake-panel">
        <div className="panel__heading compact-heading">
          <div>
            <p className="eyebrow">Synthetic case builder</p>
            <h2>Request details</h2>
          </div>
          <div className="sample-buttons" aria-label="Load sample scenario">
            <button type="button" onClick={() => loadSample('routine')}>Routine</button>
            <button type="button" onClick={() => loadSample('review')}>Review</button>
            <button type="button" onClick={() => loadSample('unsafe')}>Unsafe</button>
          </div>
        </div>

        <form onSubmit={submit} className="form-grid form-grid--compact">
          <label>Visitor name<input name="visitor_name" value={form.visitor_name} onChange={update} required /></label>
          <label>Visitor type<select name="visitor_type" value={form.visitor_type} onChange={update}>
            <option value="guest">Guest</option><option value="contractor">Contractor</option>
            <option value="delivery">Delivery</option><option value="interviewee">Interviewee</option>
          </select></label>
          <label>Organisation<input name="organisation" value={form.organisation || ''} onChange={update} /></label>

          <label>Host name<input name="host_name" value={form.host_name || ''} onChange={update} /></label>
          <label className="toggle-field">
            <span>Host confirmation</span>
            <span className="toggle-control">
              <input type="checkbox" name="host_confirmed" checked={form.host_confirmed} onChange={update} />
              <span>{form.host_confirmed ? 'Confirmed' : 'Pending'}</span>
            </span>
          </label>
          <label>Purpose<input name="visit_purpose" value={form.visit_purpose || ''} onChange={update} /></label>

          <label>Visit date<input type="date" name="visit_date" value={form.visit_date} onChange={update} required /></label>
          <label>Arrival time<input type="time" name="arrival_time" value={form.arrival_time} onChange={update} required /></label>
          <label>Duration<input type="number" name="expected_duration_minutes" min="1" max="1440" value={form.expected_duration_minutes} onChange={update} /></label>

          <label>Requested area<select name="requested_area" value={form.requested_area} onChange={update}>
            <option value="reception">Reception</option><option value="meeting_room">Meeting room</option>
            <option value="general_office">General office</option><option value="server_room">Server room</option>
            <option value="finance_office">Finance office</option><option value="control_room">Control room</option>
            <option value="data_centre">Data centre</option>
          </select></label>
          <label>Identity document<input name="identity_document_type" value={form.identity_document_type || ''} onChange={update} /></label>
          <label>Visits / 30 days<input type="number" name="visits_last_30_days" min="0" max="100" value={form.visits_last_30_days} onChange={update} /></label>

          <label className="notes-field">Additional notes<textarea name="additional_notes" value={form.additional_notes} onChange={update} rows="2" /></label>

          {error && <div className="error form-grid__wide">{error}</div>}
          <div className="form-actions form-grid__wide">
            <span>Rules validate first; model assistance never overrides security controls.</span>
            <button className="primary" disabled={busy}>{busy ? 'Running workflow…' : 'Run triage'}</button>
          </div>
        </form>
      </section>
      <ResultCard record={record} />
    </div>
  )
}
