const STATUS_COPY = {
  auto_cleared: {
    label: 'Cleared',
    tip: 'Auto-cleared by deterministic controls; no human action required.',
  },
  awaiting_human_review: {
    label: 'Review',
    tip: 'Awaiting an authorised human review decision.',
  },
  blocked: {
    label: 'Blocked',
    tip: 'Blocked by the pre-model security or deterministic control layer.',
  },
  approved: {
    label: 'Approved',
    tip: 'Approved by an authorised human reviewer.',
  },
  rejected: {
    label: 'Rejected',
    tip: 'Rejected by an authorised human reviewer.',
  },
  more_information_requested: {
    label: 'Info needed',
    tip: 'A reviewer requested more information before finalising the case.',
  },
  returned_for_correction: {
    label: 'Correction',
    tip: 'Returned for correction because required operational details are missing or unclear.',
  },
}

function titleCaseStatus(value) {
  return String(value || 'unknown')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export default function StatusBadge({ value }) {
  const safe = value || 'unknown'
  const copy = STATUS_COPY[safe] || { label: titleCaseStatus(safe), tip: titleCaseStatus(safe) }
  return (
    <span
      className={`status status--${safe}`}
      aria-label={copy.tip}
    >
      <i aria-hidden="true" />
      {copy.label}
    </span>
  )
}
