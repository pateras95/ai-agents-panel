import { createVuetify } from 'vuetify'
import { VApp, VBtn, VCard, VMain, VProgressLinear } from 'vuetify/components'
import 'vuetify/styles'

export default createVuetify({
  components: { VApp, VBtn, VCard, VMain, VProgressLinear },
  theme: {
    defaultTheme: 'nexus',
    themes: {
      nexus: {
        dark: true,
        colors: {
          background: '#10111a',
          surface: '#191b28',
          primary: '#bdb2ff',
          secondary: '#7fe0c1',
        },
      },
    },
  },
})
