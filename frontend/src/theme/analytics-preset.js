/**
 * Analytics-style preset: extends Aura with primary blue accent and semantic colors
 * for a Kibana/Grafana-like dashboard look.
 */
import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'

// Primary: blue scale (analytics/dashboard accent). Use Aura's primitive blue.
const primaryBlue = {
  50: '{blue.50}',
  100: '{blue.100}',
  200: '{blue.200}',
  300: '{blue.300}',
  400: '{blue.400}',
  500: '{blue.500}',
  600: '{blue.600}',
  700: '{blue.700}',
  800: '{blue.800}',
  900: '{blue.900}',
  950: '{blue.950}',
}

export const AnalyticsPreset = definePreset(Aura, {
  semantic: {
    primary: primaryBlue,
  },
})

export default AnalyticsPreset
