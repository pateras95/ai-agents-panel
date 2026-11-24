import { createVuetify } from 'vuetify'
import { VApp, VBtn, VCard, VDialog, VMain, VMenu } from 'vuetify/components'
import 'vuetify/styles'

export default createVuetify({
  components: { VApp, VBtn, VCard, VDialog, VMain, VMenu },
  theme: {
    defaultTheme: 'nexus',
    themes: {
      nexus: {
        dark: true,
        colors: {
          background: '#06080b',
          surface: '#0f1217',
          primary: '#e3a649',
          secondary: '#c3c3c3',
          error: '#ff8b83',
        },
      },
    },
  },
})
