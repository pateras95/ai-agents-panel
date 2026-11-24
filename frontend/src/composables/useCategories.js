// Company projects live in Bitbucket, personal ones in GitHub.
export const CATEGORY_META = {
  mpass: { label: 'MPASS', sub: 'Bitbucket', color: '#7fa8d9' },
  personal: { label: 'Personal', sub: 'GitHub', color: '#a396d6' },
  other: { label: 'Άλλο', sub: 'Χειροκίνητη γραμμή', color: '#8d96a3' },
}
const ORDER = ['mpass', 'personal', 'other']

export function categoryOf(map, name) {
  return map?.[name] ?? 'other'
}

// Splits rows into ordered category groups, keeping each row's original index for editing.
export function groupRows(rows, map) {
  return ORDER.map(key => ({
    key, ...CATEGORY_META[key],
    items: rows.map((row, index) => ({ row, index })).filter(item => categoryOf(map, item.row.name) === key),
  })).filter(group => group.items.length)
}
