/**
 * Chart theme: colors aligned with the analytics preset (and dark theme when applied).
 * Reads CSS variables so ECharts uses the same palette as the rest of the app.
 */

function getCssVar(name, fallback) {
  if (typeof document === 'undefined') return fallback
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

/** Primary/accent color for bars and highlights */
export const chartPrimaryColor = () =>
  getCssVar('--p-primary-500', '#3b82f6')

/** Grid and axis line color */
export const chartGridColor = () =>
  getCssVar('--p-surface-300', '#d1d5db')

/** Text color for axis labels and title */
export const chartTextColor = () =>
  getCssVar('--p-text-color', '#374151')

/** Tooltip background */
export const chartTooltipBg = () =>
  getCssVar('--p-surface-0', '#ffffff')

/** Object with current theme values (call when building option so it's reactive to theme switch). */
export const chartTheme = {
  get primaryColor() {
    return chartPrimaryColor()
  },
  get gridColor() {
    return chartGridColor()
  },
  get textColor() {
    return chartTextColor()
  },
  get tooltipBg() {
    return chartTooltipBg()
  },
}
