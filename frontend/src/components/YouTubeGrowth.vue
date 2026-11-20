<script setup>
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
  const source = button.closest('.youtube-copy-card')?.querySelector('[data-copy-source]')
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
  <section aria-labelledby="youtube-title" class="youtube-page">
    <header class="view-heading">
      <div>
        <h2 id="youtube-title" tabindex="-1">YouTube Growth</h2>
        <p class="muted">{{ data?.channel?.title ?? 'YouTube Analytics' }}<template v-if="data?.channel"> · Επιβεβαιωμένο κανάλι</template></p>
      </div>
      <v-btn variant="tonal" :loading="busy" @click="refresh">Ανανέωση</v-btn>
    </header>

    <nav class="youtube-cloud-links" aria-label="Έλεγχος χρήσης Google Cloud">
      <v-btn variant="outlined" size="small"
             :href="'https://console.cloud.google.com/apis/dashboard' + cloudProjectQuery"
             target="_blank" rel="noopener noreferrer">Google Cloud · Χρήση API ↗</v-btn>
      <v-btn variant="text" size="small"
             :href="'https://console.cloud.google.com/billing/linkedaccount' + cloudProjectQuery"
             target="_blank" rel="noopener noreferrer">Χρεώσεις ↗</v-btn>
    </nav>

    <p v-if="!data" role="status">Φόρτωση…</p>
    <div v-else-if="data.status !== 'connected'" class="youtube-panel" role="status">
      <h3>{{ data.status === 'unavailable' ? 'Τα στοιχεία καναλιού δεν φορτώθηκαν' : 'Σύνδεση Google' }}</h3>
      <p v-if="data.status !== 'unavailable'">
        {{ data.status === 'reauthorize' ? 'Η Google χρειάζεται νέα έγκριση.' : 'Το κανάλι δεν έχει συνδεθεί ακόμα.' }}
        Η αρχική σύνδεση γίνεται από το Ubuntu με το Lenovo συνδεδεμένο μέσω USB. Το εργαλείο σύνδεσης ανοίγει την επίσημη οθόνη συναίνεσης της Google.
      </p>
      <p v-else>Δοκίμασε ξανά την ανανέωση.</p>
    </div>

    <template v-else>
      <section class="youtube-panel youtube-analysis" aria-labelledby="youtube-analysis-title">
        <div class="view-heading">
          <h3 id="youtube-analysis-title">Προετοιμασία επόμενου upload</h3>
          <v-btn color="primary" :loading="analyzing" :disabled="!brief.trim()" @click="analyze">Ανάλυση</v-btn>
        </div>
        <label class="youtube-brief">
          Τι δείχνει το νέο βίντεο;
          <textarea v-model="brief" rows="4" maxlength="2000" :disabled="analyzing"
                    placeholder="Π.χ. διαδρομή με τη μηχανή, ποιο pub επισκεφτήκατε και τι ξεχώρισε." />
          <small class="muted">{{ brief.length }}/2000</small>
        </label>
        <div class="youtube-analysis-settings">
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
        <div v-if="mode === 'chatgpt'" class="youtube-analysis-links">
          <a href="https://chatgpt.com/settings/usage" target="_blank" rel="noopener noreferrer">Χρήση συνδρομής ChatGPT ↗</a>
          <v-btn variant="text" size="small" :loading="loadingModels" :disabled="analyzing" @click="refreshModels">Ανανέωση μοντέλων</v-btn>
        </div>
        <p v-if="mode === 'chatgpt' && catalog && catalog.status !== 'connected'" class="muted" role="status">
          {{ catalog.status === 'disconnected' ? 'Το ChatGPT δεν έχει συνδεθεί.' : 'Ο κατάλογος μοντέλων δεν είναι διαθέσιμος.' }}
        </p>
        <p v-if="analysis?.source" class="muted" role="status">
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
          <v-window v-model="resultTab" class="youtube-result">
            <v-window-item value="titles">
              <div v-if="analysis.titles.length" class="youtube-title-cards">
                <v-card v-for="(idea, index) in analysis.titles" :key="index"
                        class="youtube-copy-card" variant="outlined">
                  <div class="youtube-copy-heading">
                    <h4>Τίτλος {{ index + 1 }}</h4>
                    <v-btn color="primary" variant="tonal" :aria-label="'Αντιγραφή τίτλου ' + (index + 1)"
                           @click="copyResult(idea.text, 'title-' + index, $event)">Αντιγραφή τίτλου</v-btn>
                  </div>
                  <p class="youtube-title-text" data-copy-source>{{ idea.text }}</p>
                  <p class="muted">{{ idea.reason }}</p>
                  <p v-if="copyStatus['title-' + index]" class="muted" role="status">{{ copyStatus['title-' + index] }}</p>
                </v-card>
              </div>
              <p v-else class="muted">{{ missing }}</p>
            </v-window-item>
            <v-window-item value="thumbnails">
              <ul v-if="analysis.thumbnails?.length">
                <li v-for="idea in analysis.thumbnails" :key="idea.text"><strong>{{ idea.text }}</strong><p class="muted">{{ idea.reason }}</p></li>
              </ul>
              <p v-else class="muted">{{ missing }}</p>
            </v-window-item>
            <v-window-item value="description">
              <v-card v-if="analysis.description" class="youtube-copy-card" variant="outlined">
                <div class="youtube-copy-heading">
                  <h4>{{ analysis.source === 'local' ? 'Οι σημειώσεις σου για το βίντεο' : 'Περιγραφή για το YouTube' }}</h4>
                  <v-btn color="primary" variant="tonal" @click="copyResult(analysis.description, 'description', $event)">Αντιγραφή περιγραφής</v-btn>
                </div>
                <p class="youtube-description" data-copy-source>{{ analysis.description }}</p>
                <p v-if="copyStatus.description" class="muted" role="status">{{ copyStatus.description }}</p>
              </v-card>
              <p v-else class="muted">{{ missing }}</p>
            </v-window-item>
            <v-window-item value="tags">
              <v-card v-if="analysis.tags?.length" class="youtube-copy-card youtube-tags-card" variant="outlined">
                <div class="youtube-copy-heading">
                  <div>
                    <h4>Tags για το YouTube</h4>
                    <p class="muted">{{ analysis.tags.length }} tags · {{ analysis.tagCharacters }} / 500 χαρακτήρες</p>
                  </div>
                  <v-btn color="primary" variant="tonal" @click="copyResult(commaSeparatedTags, 'tags', $event)">Αντιγραφή όλων</v-btn>
                </div>
                <div class="youtube-tag-list">
                  <v-chip v-for="tag in analysis.tags" :key="tag" variant="outlined">{{ tag }}</v-chip>
                </div>
                <textarea data-copy-source class="youtube-tags-copy" aria-label="Tags χωρισμένα με κόμμα"
                          :value="commaSeparatedTags" rows="3" readonly spellcheck="false" />
                <p v-if="copyStatus.tags" class="muted" role="status">{{ copyStatus.tags }}</p>
              </v-card>
              <p v-else class="muted">{{ missing }}</p>
            </v-window-item>
          </v-window>
          <p class="muted" role="status">{{ analysis.note }}</p>
        </template>
        <p v-else-if="analysis" role="status">Η ανάλυση δεν ήταν διαθέσιμη.</p>
      </section>

      <p class="muted">Τελευταίες 30 ημέρες YouTube · {{ data.period.start }} έως {{ data.period.end }}<template v-if="data.period.reachDays"> · Reach: {{ data.period.reachDays }}/30 ημέρες</template></p>
      <p v-for="warning in data.warnings" :key="warning" class="notice">{{ warning }}</p>

      <h3 class="youtube-list-heading">Πρόσφατα δημόσια βίντεο</h3>
      <v-tabs v-model="videoTab" color="primary" aria-label="Τύπος δημοσιευμένων βίντεο">
        <v-tab v-for="format in videoFormats" v-show="format.id !== 'other' || videoGroups.other.length"
               :key="format.id" :value="format.id">{{ format.label }} · {{ videoGroups[format.id].length }}</v-tab>
      </v-tabs>
      <p v-if="videoTab === 'other'" class="muted">Άλλοι τύποι περιεχομένου ή βίντεο χωρίς επιβεβαιωμένη ταξινόμηση.</p>
      <p v-if="!visibleVideos.length" class="muted">Δεν βρέθηκαν δημόσια βίντεο σε αυτή την κατηγορία.</p>
      <ul v-else class="youtube-videos">
        <li v-for="video in visibleVideos" :key="video.id">
          <button type="button" class="youtube-row" :aria-expanded="expanded === video.id"
                  :aria-controls="'youtube-details-' + video.id" @click="open(video)">
            <img v-if="video.thumbnail" :src="video.thumbnail" alt="" loading="lazy" referrerpolicy="no-referrer">
            <span v-else class="youtube-thumbnail" aria-hidden="true">▶</span>
            <span class="youtube-copy">
              <span class="youtube-title-line">
                <strong>{{ video.title }}</strong><time :datetime="video.published">{{ dateFormat.format(new Date(video.published)) }}</time>
              </span>
              <span class="youtube-metrics">
                <span v-for="metric in metrics" :key="metric.key" :data-metric="metric.key">{{ metric.label }} <b>{{ display(video, metric) }}</b></span>
              </span>
            </span>
            <span class="youtube-arrow" aria-hidden="true">{{ expanded === video.id ? '−' : '+' }}</span>
          </button>
          <div v-show="expanded === video.id" :id="'youtube-details-' + video.id" class="youtube-details">
            <h4>{{ video.title }}</h4>
            <dl class="detail-list">
              <div v-for="metric in metrics" :key="metric.key"><dt>{{ metric.label }}</dt><dd>{{ display(video, metric) }}</dd></div>
            </dl>
            <h4>Διατήρηση κοινού</h4>
            <figure v-if="expanded === video.id && chart" class="youtube-chart">
              <svg viewBox="0 0 300 92" role="img" aria-label="Καμπύλη διατήρησης κοινού ως προς την πρόοδο του βίντεο">
                <path d="M0 90H300" class="youtube-chart-axis" />
                <polyline :points="chart.line" />
              </svg>
              <figcaption>Πρόοδος βίντεο 0–100% · Κλίμακα διατήρησης 0–{{ chart.maximum }}%</figcaption>
            </figure>
            <p v-else class="muted" role="status">{{ video.id in retention ? missing : 'Φόρτωση…' }}</p>
          </div>
        </li>
      </ul>
    </template>
  </section>
</template>
