import { computed } from 'vue'

export const TOOLS = [
  { name: 'Claude Code', color: '#cc8466', hint: 'Θα εμφανιστούν μετά την επόμενη απάντηση σε οποιαδήποτε συνεδρία Claude Code.' },
  { name: 'Codex', color: '#a396d6', hint: '' },
]
export const WINDOWS = [{ wire: '5ωρο', label: '5ωρο' }, { wire: '7 ημέρες', label: '7ήμερο' }]

// Green when plenty is left, amber when it runs low, red when nearly exhausted.
export function levelColor(percent) {
  if (percent === null) return 'var(--dim)'
  if (percent > 50) return '#7cc79a'
  if (percent > 20) return '#d8b56d'
  return '#df8b86'
}

export function useQuotas(limits, loading) {
  return computed(() => TOOLS.map(tool => ({
    ...tool,
    values: WINDOWS.map(window => {
      const sample = limits.value.find(item => item.tool === tool.name && item.window === window.wire)
      const remaining = sample?.remaining ?? (loading.value ? '—' : 'Μη διαθέσιμο')
      const percent = remaining.endsWith('%') ? Number.parseFloat(remaining) : null
      return {
        ...window,
        remaining,
        percent,
        reset: sample?.reset ?? 'Μη διαθέσιμο',
        updated: sample?.updated ?? 'Μη διαθέσιμο',
      }
    }),
  })))
}
