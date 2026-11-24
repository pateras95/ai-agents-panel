const shortDay = new Intl.DateTimeFormat('el-GR', { weekday: 'short', day: 'numeric', month: 'numeric', timeZone: 'UTC' })

// Muted colours that tell the projects apart in the preview.
const PALETTE = ['#7fa8d9', '#7cc79a', '#d8b56d', '#a396d6', '#df8b86', '#62bdb0', '#cc8466']

// One entry per project with its days, company projects first. Personal projects are left out unless asked for.
export function groupWeekProjects(days, categories, includePersonal = false) {
  const projects = new Map()
  for (const day of days) {
    for (const row of day.rows) {
      const name = row.name || 'Άλλο'
      const category = categories[name] ?? 'other'
      if (category !== 'mpass' && !includePersonal) continue
      if (!projects.has(name)) projects.set(name, { name, category, items: [] })
      projects.get(name).items.push({ date: day.date, day: shortDay.format(new Date(day.date + 'T00:00:00Z')), text: row.text })
    }
  }
  const order = ['mpass', 'personal', 'other']
  return [...projects.values()]
    .sort((a, b) => order.indexOf(a.category) - order.indexOf(b.category))
    .map((project, index) => ({ ...project, color: PALETTE[index % PALETTE.length], summary: project.items.map(item => item.text.replace(/\.$/, '')).join('. ') + '.' }))
}

// The same content as plain text for e-mail or Slack.
export function buildWeekExport(projects, range, mode = 'days') {
  const lines = [`Εβδομάδα ${range}`, '']
  for (const project of projects) {
    lines.push(project.name)
    if (mode === 'summary') lines.push('• ' + project.summary)
    else for (const item of project.items) lines.push(`• ${item.day}: ${item.text}`)
    lines.push('')
  }
  if (!projects.length) lines.push('Δεν υπάρχει καταγεγραμμένη δουλειά για αυτή την εβδομάδα.')
  return lines.join('\n').trim() + '\n'
}

// The page is served over plain HTTP, so the Clipboard API may be missing: fall back to a hidden field.
export async function copyText(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch { /* fall through */ }
  const field = document.createElement('textarea')
  field.value = text
  field.readOnly = true
  field.style.cssText = 'position:fixed;top:0;left:0;opacity:0'
  document.body.append(field)
  try {
    field.focus({ preventScroll: true })
    field.select()
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    field.remove()
  }
}
