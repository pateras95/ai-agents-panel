<script setup>
import { nextTick, ref } from 'vue'

defineProps({ items: Array, active: String, mobile: Boolean })
defineEmits(['navigate'])
const open = ref(false)
const trigger = ref(null)

async function close(focus = false) {
  open.value = false
  if (focus) {
    await nextTick()
    trigger.value?.$el.focus()
  }
}
</script>

<template>
  <aside v-if="!mobile" class="desktop-menu">
    <nav aria-label="Κύρια πλοήγηση">
      <a v-for="item in items" :key="item.id" :href="'#' + item.id"
         :aria-current="active === item.id ? 'page' : undefined"
         @click.prevent="$emit('navigate', item.id)">{{ item.label }}</a>
    </nav>
  </aside>
  <div v-else class="mobile-menu" @keydown.esc="close(true)">
    <v-btn ref="trigger" variant="tonal" color="primary" :aria-expanded="open"
           aria-controls="mobile-links" @click="open = !open">
      <span aria-hidden="true" class="menu-mark">☰</span> Μενού
    </v-btn>
    <nav v-show="open" id="mobile-links" aria-label="Κύρια πλοήγηση">
      <a v-for="item in items" :key="item.id" :href="'#' + item.id"
         :aria-current="active === item.id ? 'page' : undefined"
         @click.prevent="$emit('navigate', item.id); close()">{{ item.label }}</a>
    </nav>
  </div>
</template>
