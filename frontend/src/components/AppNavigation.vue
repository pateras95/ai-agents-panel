<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({ items: Array, active: String })
const emit = defineEmits(['navigate'])
const bar = ref(null)

// Keep the active tab visible when the pager is swiped.
watch(() => props.active, async () => {
  await nextTick()
  // Scroll only the tab bar itself; scrollIntoView would also pan the whole page.
  const tab = bar.value?.querySelector('[aria-selected="true"]')
  if (tab) bar.value.scrollTo({ left: tab.offsetLeft - (bar.value.clientWidth - tab.clientWidth) / 2, behavior: 'smooth' })
})
</script>

<template>
  <nav ref="bar" class="tabbar" role="tablist" aria-label="Κύρια πλοήγηση">
    <button v-for="item in items" :key="item.id" type="button" role="tab" class="tab"
            :aria-selected="active === item.id" :tabindex="active === item.id ? 0 : -1"
            @click="emit('navigate', item.id)">{{ item.short ?? item.label }}</button>
  </nav>
</template>
