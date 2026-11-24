// One shared definition of a stand-up line: "Project: sentence".
export function parseLine(line) {
  const separator = line.indexOf(':')
  return separator > 0
    ? { name: line.slice(0, separator).trim(), text: line.slice(separator + 1).trim() }
    : { name: '', text: line.trim() }
}

export function formatLine(row) {
  const text = row.text.trim()
  return row.name.trim() ? `${row.name.trim()}: ${text}` : text
}

export function rowsFromReport(report) {
  return (report?.sections[0]?.items ?? []).map(parseLine)
}

export function rowsFromProjects(projects) {
  return projects.map(project => ({ name: project.name, text: project.summary }))
}
