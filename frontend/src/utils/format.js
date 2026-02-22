/**
 * Format a duration in seconds dynamically: seconds only (&lt; 1 min), M:SS (&lt; 1 h), or H:MM:SS.
 *
 * @param {number} sec - Duration in seconds (float; will be floored). Null/undefined/NaN treated as 0.
 * @returns {string} - e.g. "45 s", "1:23", "1:23:45"
 */
export function formatDuration(sec) {
  const s = Math.max(0, Math.floor(Number(sec) || 0))
  if (s < 60) return `${s} s`
  if (s < 3600) {
    const m = Math.floor(s / 60)
    const ss = s % 60
    return `${m}:${String(ss).padStart(2, '0')}`
  }
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = s % 60
  return `${h}:${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

/**
 * Unit suffix for a duration value, matching formatDuration: (s), (min), or (h).
 *
 * @param {number} sec - Duration in seconds.
 * @returns {string} - "(s)", "(min)", or "(h)"
 */
function getDurationUnitSuffix(sec) {
  const s = Math.max(0, Math.floor(Number(sec) || 0))
  if (s < 60) return '(s)'
  if (s < 3600) return '(min)'
  return '(h)'
}

/**
 * Return a stat label with the unit suffix updated to match the duration visualization.
 * Strips any trailing parenthesized unit (e.g. " (sec)") and appends (s), (min), or (h) based on value.
 *
 * @param {string} label - Stat label from definitions, e.g. "Longest talk (sec)".
 * @param {number} sec - Duration in seconds (the stat value).
 * @returns {string} - e.g. "Longest talk (s)", "Longest talk (min)", "Longest talk (h)"
 */
export function formatDurationStatLabel(label, sec) {
  const base = String(label || '').replace(/\s*\([^)]*\)\s*$/, '').trim()
  const suffix = getDurationUnitSuffix(sec)
  return base ? `${base} ${suffix}` : suffix
}

/**
 * Format a duration in seconds as H:MM:SS or HH:MM:SS.
 * Minutes and seconds are zero-padded to two digits.
 *
 * @param {number} sec - Duration in seconds (float; will be floored). Null/undefined/NaN treated as 0.
 * @returns {string} - e.g. "0:01:05", "1:23:45"
 */
export function secondsToHhMmSs(sec) {
  const s = Math.max(0, Math.floor(Number(sec) || 0))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = s % 60
  return `${h}:${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}
