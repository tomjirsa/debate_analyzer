/**
 * Polaris-like theme preset.
 *
 * PrimeVue styling is driven by CSS variables (see PrimeUI theme + `@primeuix/themes`).
 * We keep the base Aura preset and leave the "Polaris" palette adjustments to CSS
 * variable overrides in `frontend/src/assets/main.css` so we don't depend on
 * specific color primitives being available in the theme package.
 */
import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'

// Keep a blue primary scale as the base; we'll override `--p-primary-*` in CSS.
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

export const PolarisPreset = definePreset(Aura, {
  semantic: {
    primary: primaryBlue,
  },
})

export default PolarisPreset

