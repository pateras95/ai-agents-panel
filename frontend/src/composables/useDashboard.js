import { onMounted, ref } from 'vue'

export function useDashboard() {
  const dashboard = ref(null)
  const loading = ref(false)
  const error = ref(false)

  async function refresh() {
    if (loading.value) return
    loading.value = true
    error.value = false
    try {
      const response = await fetch('/api/dashboard', { cache: 'no-store' })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      dashboard.value = await response.json()
    } catch {
      error.value = true
    } finally {
      loading.value = false
    }
  }

  onMounted(refresh)
  return { dashboard, loading, error, refresh }
}
