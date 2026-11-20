<script setup>
import { ref } from 'vue'

defineProps({ items: Array, active: String })
const emit = defineEmits(['navigate'])
const open = ref(false)

function choose(id) {
  open.value = false
  emit('navigate', id)
}
</script>

<template>
  <v-menu v-model="open" location="bottom end" :offset="8" :close-on-content-click="false"
          content-class="navigation-popover">
    <template #activator="{ props }">
      <v-btn v-bind="props" class="menu-toggle" variant="text" aria-label="Μενού">
        <span class="hamburger" aria-hidden="true"><i></i><i></i><i></i></span>
      </v-btn>
    </template>
    <nav class="navigation-links" role="menu" aria-label="Κύρια πλοήγηση">
      <a v-for="item in items" :key="item.id" :href="'#' + item.id" role="menuitem"
         :aria-current="active === item.id ? 'page' : undefined"
         @click.prevent="choose(item.id)">{{ item.label }}</a>
    </nav>
  </v-menu>
</template>
