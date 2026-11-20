import { onMounted, onUnmounted, ref } from 'vue'

const REPORT_POLL_MS = 5000
const LIMIT_POLL_MS = 120000

export function useDashboard() {
  const limits = ref([])
  const loading = ref(false)
  const error = ref(false)
  const reports = ref([])
  const reportError = ref(false)
  let reportRequest
  let reportPoll
  let lastLimitCheck = 0
  let limitRequest

  async function refreshLimits() {
    if (loading.value) return
    loading.value = true
    error.value = false
    lastLimitCheck = Date.now()
    const controller = new AbortController()
    limitRequest = controller
    const timeout = setTimeout(() => controller.abort(), 22500)
    try {
      const response = await fetch('/api/limits', { cache: 'no-store', signal: controller.signal })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      limits.value = (await response.json()).limits
    } catch {
      error.value = true
    } finally {
      clearTimeout(timeout)
      if (limitRequest === controller) limitRequest = undefined
      loading.value = false
    }
  }

  async function refreshReports(force = false) {
    if (reportRequest && !force) return
    reportRequest?.abort()
    const controller = new AbortController()
    reportRequest = controller
    const timeout = setTimeout(() => controller.abort(), 4500)
    try {
      const response = await fetch('/api/reports', {
        cache: 'no-store',
        signal: controller.signal,
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const snapshot = (await response.json()).reports
      if (reportRequest === controller) {
        reports.value = snapshot
        reportError.value = false
      }
    } catch {
      if (reportRequest === controller) reportError.value = true
    } finally {
      clearTimeout(timeout)
      if (reportRequest === controller) reportRequest = undefined
    }
  }

  function syncVisible() {
    if (document.hidden) return
    void refreshReports()
    if (Date.now() - lastLimitCheck >= LIMIT_POLL_MS) void refreshLimits()
  }

  onMounted(() => {
    syncVisible()
    reportPoll = setInterval(syncVisible, REPORT_POLL_MS)
    document.addEventListener('visibilitychange', syncVisible)
    window.addEventListener('pageshow', syncVisible)
    window.addEventListener('focus', syncVisible)
  })
  onUnmounted(() => {
    clearInterval(reportPoll)
    limitRequest?.abort()
    const activeRequest = reportRequest
    reportRequest = undefined
    activeRequest?.abort()
    document.removeEventListener('visibilitychange', syncVisible)
    window.removeEventListener('pageshow', syncVisible)
    window.removeEventListener('focus', syncVisible)
  })
  return { limits, loading, error, refreshLimits, reports, reportError, refreshReports }
}
