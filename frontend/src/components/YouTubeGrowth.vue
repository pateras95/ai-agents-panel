<script setup>
import '../styles/youtube.css'
import { computed, onMounted, ref, watch } from 'vue'
import { VChip, VTab, VTabs, VWindow, VWindowItem } from 'vuetify/components'

const data = ref(null)
const busy = ref(false)
const cloudProjectQuery = computed(() => data.value?.cloudProject
  ? '?' + new URLSearchParams({ project: data.value.cloudProject })
  : '')
const analysis = ref(null)
const analyzing = ref(false)
const brief = ref('')
const uploadFormat = ref('long')
const resultTab = ref('titles')
const copyStatus = ref({})
const commaSeparatedTags = computed(() => (analysis.value?.tags ?? []).join(','))

async function copyResult(text, key, event) {
  const button = event.currentTarget
  const source = button.closest('.yt-copy-card')?.querySelector('[data-copy-source]')
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const field = document.createElement('textarea')
      field.value = text
      field.readOnly = true
      field.style.cssText = 'position:fixed;top:0;left:0;opacity:0'
      document.body.append(field)
      try {
        field.focus({ preventScroll: true })
        field.select()
        if (!document.execCommand('copy')) throw new Error('Clipboard unavailable')
      } finally {
        field.remove()
        button.focus({ preventScroll: true })
      }
    }
    copyStatus.value[key] = 'Αντιγράφηκε.'
  } catch {
    if (source instanceof HTMLTextAreaElement) {
      source.focus({ preventScroll: true })
      source.select()
    } else if (source) {
      const range = document.createRange()
      range.selectNodeContents(source)
      const selection = window.getSelection()
      selection.removeAllRanges()
      selection.addRange(range)
    }
    copyStatus.value[key] = 'Κάνε αντιγραφή από το μενού της συσκευής σου.'
  }
}
const videoTab = ref('long')
const videoFormats = [
  { id: 'long', label: 'Long videos' },
  { id: 'short', label: 'Shorts videos' },
  { id: 'other', label: 'Λοιπά' },
]
const videoGroups = computed(() => Object.fromEntries(videoFormats.map(({ id }) => [
  id, (data.value?.videos ?? []).filter(video => (video.format ?? 'other') === id),
])))
const visibleVideos = computed(() => videoGroups.value[videoTab.value])
const resultTabs = [
  { id: 'titles', label: 'Τίτλοι' },
  { id: 'description', label: 'Περιγραφή' },
  { id: 'tags', label: 'Tags' },
  { id: 'thumbnails', label: 'Thumbnails' },
]
const catalog = ref(null)
const loadingModels = ref(false)
let preferences = {}
try {
  preferences = JSON.parse(localStorage.getItem('nexus-youtube-analysis') ?? '{}') ?? {}
} catch {
  // The settings also work when browser storage is unavailable.
}
const mode = ref(preferences.mode === 'local' ? 'local' : 'chatgpt')
const model = ref(typeof preferences.model === 'string' ? preferences.model : '')
const counts = [5, 10, 15, 25]
const count = ref(counts.includes(preferences.count) ? preferences.count : 15)
watch([mode, model, count], () => {
  try {
    localStorage.setItem('nexus-youtube-analysis', JSON.stringify({
      mode: mode.value, model: model.value, count: count.value,
    }))
  } catch {
    // Keep settings in memory for this visit.
  }
})
const expanded = ref(null)
const retention = ref({})
const pending = new Set()
const missing = 'Μη διαθέσιμο'
const metrics = [
  { key: 'impressions', label: 'Impressions', digits: 0 },
  { key: 'ctr', label: 'CTR', digits: 1, suffix: '%' },
  { key: 'average', label: 'Μέσο ποσοστό προβολής', digits: 1, suffix: '%' },
  { key: 'hours', label: 'Ώρες θέασης', digits: 2 },
  { key: 'subscribers', label: 'Μεταβολή συνδρομητών', digits: 0 },
]
const dateFormat = new Intl.DateTimeFormat('el-GR', { dateStyle: 'medium', timeZone: 'Europe/Athens' })
const display = (video, metric) => Number.isFinite(video[metric.key])
  ? new Intl.NumberFormat('el-GR', { maximumFractionDigits: metric.digits,
    signDisplay: metric.key === 'subscribers' ? 'exceptZero' : 'auto' }).format(video[metric.key]) + (metric.suffix ?? '')
  : missing

async function load(path, method = 'GET', payload) {
  try {
    const response = await fetch('/api/youtube/' + path, {
      cache: 'no-store', method,
      ...(payload ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) } : {}),
    })
    if (response.ok) return await response.json()
  } catch {
    // Keep local connection errors distinct from empty reports.
  }
  return { status: 'unavailable' }
}

async function refresh() {
  busy.value = true
  data.value = await load('videos')
  busy.value = false
}

async function open(video) {
  expanded.value = expanded.value === video.id ? null : video.id
  if (!expanded.value || video.id in retention.value || pending.has(video.id)) return
  pending.add(video.id)
  try {
    const result = await load('retention?video=' + encodeURIComponent(video.id))
    retention.value[video.id] = result.points ?? []
  } finally {
    pending.delete(video.id)
  }
}

async function refreshModels() {
  loadingModels.value = true
  const next = await load('models')
  catalog.value = next
  if (next.status === 'connected' && !next.models?.some(item => item.slug === model.value)) model.value = ''
  loadingModels.value = false
}

async function analyze() {
  if (!brief.value.trim()) return
  analyzing.value = true
  const options = new URLSearchParams({ mode: mode.value, model: model.value, count: count.value })
  analysis.value = await load('analysis?' + options, 'POST', { brief: brief.value.trim(), format: uploadFormat.value })
  resultTab.value = 'titles'
  copyStatus.value = {}
  analyzing.value = false
}

const chart = computed(() => {
  const points = retention.value[expanded.value] ?? []
  if (!points.length) return null
  const maximum = Math.max(1, ...points.map(point => point[1]))
  return { maximum: Math.ceil(maximum * 100),
    line: points.map(([elapsed, ratio]) => `${elapsed * 300},${90 - ratio * 85 / maximum}`).join(' ') }
})
onMounted(() => {
  void refresh()
  if (mode.value === 'chatgpt') void refreshModels()
})
watch(mode, value => { if (value === 'chatgpt' && !catalog.value) void refreshModels() })
</script>

<template>
  <section aria-labelledby="youtube-title" class="yt-page">
    <header class="yt-head">
      <div>
        <h2 id="youtube-title" tabindex="-1">YouTube Growth</h2>
        <p class="yt-muted">{{ data?.channel?.title ?? 'YouTube Analytics' }}<template v-if="data?.channel"> · Επιβεβαιωμένο κανάλι</template></p>
      </div>
      <div class="yt-head-actions">
      <nav class="yt-cloud-links" aria-label="Έλεγχος χρήσης Google Cloud">
      <v-btn variant="outlined" size="small"
             :href="'https://console.cloud.google.com/apis/dashboard' + cloudProjectQuery"
             target="_blank" rel="noopener noreferrer">Google Cloud · Χρήση API ↗</v-btn>
      <v-btn variant="text" size="small"
             :href="'https://console.cloud.google.com/billing/linkedaccount' + cloudProjectQuery"
             target="_blank" rel="noopener noreferrer">Χρεώσεις ↗</v-btn>
    </nav>
        <v-btn variant="tonal" :loading="busy" @click="refresh">Ανανέωση</v-btn>
      </div>
    </header>


    <p v-if="!data" role="status">Φόρτωση…</p>
    <div v-else-if="data.status !== 'connected'" class="yt-panel" role="status">
      <h3>{{ data.status === 'unavailable' ? 'Τα στοιχεία καναλιού δεν φορτώθηκαν' : 'Σύνδεση Google' }}</h3>
      <p v-if="data.status !== 'unavailable'">
        {{ data.status === 'reauthorize' ? 'Η Google χρειάζεται νέα έγκριση.' : 'Το κανάλι δεν έχει συνδεθεί ακόμα.' }}
        Η αρχική σύνδεση γίνεται από το Ubuntu με το Lenovo συνδεδεμένο μέσω USB. Το εργαλείο σύνδεσης ανοίγει την επίσημη οθόνη συναίνεσης της Google.
      </p>
      <p v-else>Δοκίμασε ξανά την ανανέωση.</p>
    </div>

    <template v-else>
      <div class="yt-prep">
      <section class="yt-panel yt-analysis" aria-labelledby="youtube-analysis-title">
        <div class="yt-head">
          <h3 id="youtube-analysis-title">Προετοιμασία επόμενου upload</h3>
          <v-btn color="primary" :loading="analyzing" :disabled="!brief.trim()" @click="analyze">Ανάλυση</v-btn>
        </div>
        <label class="yt-brief">
          Τι δείχνει το νέο βίντεο;
          <textarea v-model="brief" rows="4" maxlength="2000" :disabled="analyzing"
                    placeholder="Π.χ. διαδρομή με τη μηχανή, ποιο pub επισκεφτήκατε και τι ξεχώρισε." />
          <small class="yt-muted">{{ brief.length }}/2000</small>
        </label>
        <div class="yt-analysis-settings">
          <label>Τύπος νέου βίντεο
            <select v-model="uploadFormat" :disabled="analyzing">
              <option value="long">Long video</option>
              <option value="short">Short</option>
            </select>
          </label>
          <label>Τρόπος ανάλυσης
            <select v-model="mode" :disabled="analyzing">
              <option value="chatgpt">ChatGPT με συνδρομή</option>
              <option value="local">Μόνο τοπική</option>
            </select>
          </label>
          <template v-if="mode === 'chatgpt'">
            <label>Μοντέλο ChatGPT
              <select v-model="model" :disabled="analyzing || loadingModels || !catalog?.models?.length">
                <option value="">Αυτόματη επιλογή</option>
                <option v-for="option in catalog?.models" :key="option.slug" :value="option.slug">{{ option.label }}</option>
              </select>
            </label>
            <label>Πρόσφατα βίντεο για το ChatGPT
              <select v-model.number="count" :disabled="analyzing">
                <option v-for="size in counts" :key="size" :value="size">{{ size }}</option>
              </select>
            </label>
          </template>
        </div>
        <div v-if="mode === 'chatgpt'" class="yt-analysis-links">
          <a href="https://chatgpt.com/settings/usage" target="_blank" rel="noopener noreferrer">Χρήση συνδρομής ChatGPT ↗</a>
          <v-btn variant="text" size="small" :loading="loadingModels" :disabled="analyzing" @click="refreshModels">Ανανέωση μοντέλων</v-btn>
        </div>
        <p v-if="mode === 'chatgpt' && catalog && catalog.status !== 'connected'" class="yt-muted" role="status">
          {{ catalog.status === 'disconnected' ? 'Το ChatGPT δεν έχει συνδεθεί.' : 'Ο κατάλογος μοντέλων δεν είναι διαθέσιμος.' }}
        </p>
        <p v-if="analysis?.source" class="yt-muted" role="status">
          {{ analysis.source === 'chatgpt' ? 'Ανάλυση με ChatGPT' : 'Τοπική ανάλυση' }}
          <template v-if="analysis.model"> · {{ analysis.model }} · {{ analysis.videoCount }} βίντεο</template>
          <template v-if="analysis.fallback === 'limit'"> · Όριο χρήσης ChatGPT</template>
          <template v-else-if="analysis.fallback === 'unavailable'"> · Το ChatGPT δεν είναι διαθέσιμο</template>
          <template v-else-if="analysis.fallback === 'disconnected'"> · Το ChatGPT δεν έχει συνδεθεί</template>
          <template v-else-if="analysis.fallback === 'insufficient'"> · Λίγα διαθέσιμα στοιχεία</template>
        </p>
        <template v-if="analysis?.titles">
          <v-tabs v-model="resultTab" color="primary" aria-label="Προτάσεις για το βίντεο">
            <v-tab v-for="tab in resultTabs" :key="tab.id" :value="tab.id">{{ tab.label }}</v-tab>
          </v-tabs>
          <v-window v-model="resultTab" class="yt-result">
            <v-window-item value="titles">
              <div v-if="analysis.titles.length" class="yt-title-cards">
                <v-card v-for="(idea, index) in analysis.titles" :key="index"
                        class="yt-copy-card" variant="outlined">
                  <div class="yt-copy-heading">
                    <h4>Τίτλος {{ index + 1 }}</h4>
                    <v-btn color="primary" variant="tonal" :aria-label="'Αντιγραφή τίτλου ' + (index + 1)"
                           @click="copyResult(idea.text, 'title-' + index, $event)">Αντιγραφή τίτλου</v-btn>
                  </div>
                  <p class="yt-title-text" data-copy-source>{{ idea.text }}</p>
                  <p class="yt-muted">{{ idea.reason }}</p>
                  <p v-if="copyStatus['title-' + index]" class="yt-muted" role="status">{{ copyStatus['title-' + index] }}</p>
                </v-card>
              </div>
              <p v-else class="yt-muted">{{ missing }}</p>
            </v-window-item>
            <v-window-item value="thumbnails">
              <ul v-if="analysis.thumbnails?.length">
                <li v-for="idea in analysis.thumbnails" :key="idea.text"><strong>{{ idea.text }}</strong><p class="yt-muted">{{ idea.reason }}</p></li>
              </ul>
              <p v-else class="yt-muted">{{ missing }}</p>
            </v-window-item>
            <v-window-item value="description">
              <v-card v-if="analysis.description" class="yt-copy-card" variant="outlined">
                <div class="yt-copy-heading">
                  <h4>{{ analysis.source === 'local' ? 'Οι σημειώσεις σου για το βίντεο' : 'Περιγραφή για το YouTube' }}</h4>
                  <v-btn color="primary" variant="tonal" @click="copyResult(analysis.description, 'description', $event)">Αντιγραφή περιγραφής</v-btn>
                </div>
                <p class="yt-description" data-copy-source>{{ analysis.description }}</p>
                <p v-if="copyStatus.description" class="yt-muted" role="status">{{ copyStatus.description }}</p>
              </v-card>
              <p v-else class="yt-muted">{{ missing }}</p>
            </v-window-item>
            <v-window-item value="tags">
              <v-card v-if="analysis.tags?.length" class="yt-copy-card yt-tags-card" variant="outlined">
                <div class="yt-copy-heading">
                  <div>
                    <h4>Tags για το YouTube</h4>
                    <p class="yt-muted">{{ analysis.tags.length }} tags · {{ analysis.tagCharacters }} / 500 χαρακτήρες</p>
                  </div>
                  <v-btn color="primary" variant="tonal" @click="copyResult(commaSeparatedTags, 'tags', $event)">Αντιγραφή όλων</v-btn>
                </div>
                <div class="yt-tag-list">
                  <v-chip v-for="tag in analysis.tags" :key="tag" variant="outlined">{{ tag }}</v-chip>
                </div>
                <textarea data-copy-source class="yt-tags-copy" aria-label="Tags χωρισμένα με κόμμα"
                          :value="commaSeparatedTags" rows="3" readonly spellcheck="false" />
                <p v-if="copyStatus.tags" class="yt-muted" role="status">{{ copyStatus.tags }}</p>
              </v-card>
              <p v-else class="yt-muted">{{ missing }}</p>
            </v-window-item>
          </v-window>
          <p class="yt-muted" role="status">{{ analysis.note }}</p>
        </template>
        <p v-else-if="analysis" role="status">Η ανάλυση δεν ήταν διαθέσιμη.</p>
      </section>
      </div>

      <p class="yt-muted">Τελευταίες 30 ημέρες YouTube · {{ data.period.start }} έως {{ data.period.end }}<template v-if="data.period.reachDays"> · Reach: {{ data.period.reachDays }}/30 ημέρες</template></p>
      <p v-for="warning in data.warnings" :key="warning" class="yt-notice">{{ warning }}</p>

      <div class="yt-kpis" role="group" aria-label="Σύνοψη βίντεο">
        <div class="yt-kpi" style="--yt-accent: #d9696a"><span class="yt-kpi-label">Βίντεο</span><b>{{ data.videos?.length ?? 0 }}</b></div>
        <div class="yt-kpi" style="--yt-accent: #7fa8d9"><span class="yt-kpi-label">Impressions</span><b>{{ display({ v: (data.videos ?? []).reduce((sum, v) => sum + (Number.isFinite(v.impressions) ? v.impressions : 0), 0) }, { key: 'v', digits: 0 }) }}</b></div>
        <div class="yt-kpi" style="--yt-accent: #7cc79a"><span class="yt-kpi-label">Ώρες θέασης</span><b>{{ display({ v: (data.videos ?? []).reduce((sum, v) => sum + (Number.isFinite(v.hours) ? v.hours : 0), 0) }, { key: 'v', digits: 1 }) }}</b></div>
        <div class="yt-kpi" style="--yt-accent: #d8b56d"><span class="yt-kpi-label">Μεταβολή συνδρομητών</span><b>{{ display({ v: (data.videos ?? []).reduce((sum, v) => sum + (Number.isFinite(v.subscribers) ? v.subscribers : 0), 0) }, { key: 'v', digits: 0 }) }}</b></div>
      </div>

      <h3 class="yt-list-heading">Πρόσφατα δημόσια βίντεο</h3>
      <v-tabs v-model="videoTab" color="primary" aria-label="Τύπος δημοσιευμένων βίντεο">
        <v-tab v-for="format in videoFormats" v-show="format.id !== 'other' || videoGroups.other.length"
               :key="format.id" :value="format.id">{{ format.label }} · {{ videoGroups[format.id].length }}</v-tab>
      </v-tabs>
      <p v-if="videoTab === 'other'" class="yt-muted">Άλλοι τύποι περιεχομένου ή βίντεο χωρίς επιβεβαιωμένη ταξινόμηση.</p>
      <p v-if="!visibleVideos.length" class="yt-muted">Δεν βρέθηκαν δημόσια βίντεο σε αυτή την κατηγορία.</p>
      <ul v-else class="yt-videos">
        <li v-for="video in visibleVideos" :key="video.id">
          <button type="button" class="yt-row" :aria-expanded="expanded === video.id"
                  :aria-controls="'youtube-details-' + video.id" @click="open(video)">
            <img v-if="video.thumbnail" :src="video.thumbnail" alt="" loading="lazy" referrerpolicy="no-referrer">
            <span v-else class="yt-thumbnail" aria-hidden="true">▶</span>
            <span class="yt-copy">
              <span class="yt-title-line">
                <strong>{{ video.title }}</strong><time :datetime="video.published">{{ dateFormat.format(new Date(video.published)) }}</time>
              </span>
              <span class="yt-metrics">
                <span v-for="metric in metrics" :key="metric.key" :data-metric="metric.key">{{ metric.label }} <b>{{ display(video, metric) }}</b></span>
              </span>
            </span>
            <span class="yt-arrow" aria-hidden="true">{{ expanded === video.id ? '−' : '+' }}</span>
          </button>
          <div v-show="expanded === video.id" :id="'youtube-details-' + video.id" class="yt-details">
            <h4>{{ video.title }}</h4>
            <dl class="yt-stats">
              <div v-for="metric in metrics" :key="metric.key"><dt>{{ metric.label }}</dt><dd>{{ display(video, metric) }}</dd></div>
            </dl>
            <h4>Διατήρηση κοινού</h4>
            <figure v-if="expanded === video.id && chart" class="yt-chart">
              <svg viewBox="0 0 300 92" role="img" aria-label="Καμπύλη διατήρησης κοινού ως προς την πρόοδο του βίντεο">
                <path d="M0 90H300" class="yt-chart-axis" />
                <polyline :points="chart.line" />
              </svg>
              <figcaption>Πρόοδος βίντεο 0–100% · Κλίμακα διατήρησης 0–{{ chart.maximum }}%</figcaption>
            </figure>
            <p v-else class="yt-muted" role="status">{{ video.id in retention ? missing : 'Φόρτωση…' }}</p>
          </div>
        </li>
      </ul>
    </template>
  </section>
</template>
