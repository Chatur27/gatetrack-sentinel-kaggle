import StatusBadge from './StatusBadge.jsx'

function provenance(review) {
  if (!review) return null
  if (review.fallback_used) return ['Safe fallback', 'fallback']
  if (review.model_invoked) return ['Gemini via ADK', 'live']
  return ['Deterministic mock', 'mock']
}

export default function ResultCard({ record }) {
  if (!record) {
    return (
      <section className="result-card result-card--empty">
        <div className="empty-visual">GS</div>
        <p className="eyebrow">Live outcome</p>
        <h3>Ready for a synthetic case</h3>
        <p>Choose a scenario or edit the request. The decision panel will show routing, policy grounding, security status and human-review requirements.</p>
        <div className="empty-steps">
          <span>1 · Validate</span><span>2 · Secure</span><span>3 · Route</span><span>4 · Record</span>
        </div>
      </section>
    )
  }

  const source = provenance(record.review)

  return (
    <section className="result-card" aria-live="polite">
      <div className="result-card__header">
        <div>
          <p className="eyebrow">Case outcome</p>
          <h3>{record.case_id}</h3>
        </div>
        <StatusBadge value={record.status} />
      </div>

      <div className="metric-grid">
        <div><span>Route</span><strong>{record.risk.route.replaceAll('_', ' ')}</strong></div>
        <div><span>Risk</span><strong>{record.risk.score}</strong></div>
        <div><span>Security</span><strong>{record.security?.status || 'not run'}</strong></div>
        <div><span>Policy</span><strong>{record.policies?.[0]?.id || 'none'}</strong></div>
      </div>

      {record.review ? (
        <>
          <div className={`agent-provenance agent-provenance--${source[1]}`}>
            <div>
              <span>Review source</span>
              <strong>{source[0]}</strong>
            </div>
            <div>
              <span>Model</span>
              <strong>{record.review.model_name || 'deterministic-mock'}</strong>
            </div>
            <div>
              <span>MCP / elapsed</span>
              <strong>{record.review.tool_calls?.length || 0} calls · {record.review.latency_ms || 0} ms</strong>
            </div>
          </div>
          {record.review.fallback_used && record.review.fallback_reason ? (
            <div className="fallback-diagnostic" role="status">
              <span>Fallback: <strong>{record.review.fallback_reason.replaceAll('_', ' ')}</strong></span>
              <span>Stage: <strong>{(record.review.failure_stage || 'preflight').replaceAll('_', ' ')}</strong></span>
              <span>Attempts: <strong>{record.review.attempt_count || 0}</strong></span>
            </div>
          ) : null}
          {!record.review.fallback_used && (record.review.repair_used || record.review.mcp_connection_reused) ? (
            <div className="agent-diagnostic" role="status">
              {record.review.mcp_connection_reused ? <span>MCP warm connection reused</span> : null}
              {record.review.repair_used ? <span>JSON locally normalised</span> : null}
            </div>
          ) : null}
          <div className="callout compact-callout">
            <strong>Bounded review</strong>
            <p>{record.review.summary}</p>
            <small>{record.review.limitations}</small>
          </div>
        </>
      ) : (
        <div className="callout compact-callout callout--blocked">
          <strong>Pre-model security gate</strong>
          <p>The input was blocked before any model review could run.</p>
          <small>Human authority is required for the next permitted action.</small>
        </div>
      )}

      <div className="factor-section">
        <div className="section-label"><span>Triggered factors</span><strong>{record.risk.factors.length}</strong></div>
        {record.risk.factors.length > 0 ? (
          <ul className="factor-list">
            {record.risk.factors.map((factor) => (
              <li key={factor.code}>
                <span>{factor.code.replaceAll('_', ' ')}</span>
                <strong>+{factor.points}</strong>
              </li>
            ))}
          </ul>
        ) : <p className="empty compact-empty">No elevated rule factors.</p>}
      </div>
    </section>
  )
}
