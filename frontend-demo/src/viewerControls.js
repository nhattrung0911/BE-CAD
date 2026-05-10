// Pure helpers for the 3D viewer's camera + auto-rotate behavior.
// Kept as plain functions (no React, no three.js objects) so they can be
// unit-tested in isolation under vitest with no DOM/WebGL stub.

/**
 * Auto-rotate angular speed (in OrbitControls units, where 1.0 ≈ 30°/s).
 * Larger parts feel slower at the same angular speed because more pixels
 * sweep per second; we damp accordingly so an M2 washer and an M30 bolt
 * both feel similar on screen.
 *
 * @param {{size?: number[]} | null | undefined} bbox Optional bbox with size=[sx,sy,sz] in mm.
 * @param {object} [options]
 * @param {number} [options.base=1.4]   Speed when bbox missing or tiny.
 * @param {number} [options.minSpeed=0.4]
 * @param {number} [options.maxSpeed=1.6]
 * @returns {number}
 */
export function computeAutoRotateSpeed(bbox, options = {}) {
  const base = options.base ?? 1.4;
  const minSpeed = options.minSpeed ?? 0.4;
  const maxSpeed = options.maxSpeed ?? 1.6;
  if (!bbox || !Array.isArray(bbox.size) || bbox.size.length < 3) return base;
  const longest = Math.max(...bbox.size.map((v) => Number(v) || 0));
  if (!Number.isFinite(longest) || longest <= 0) return base;
  // Reference part: 30 mm long (M8x30 hex bolt). Smaller → faster, larger → slower.
  const ratio = 30 / longest;
  const speed = base * Math.cbrt(ratio);
  return Math.min(maxSpeed, Math.max(minSpeed, speed));
}

/**
 * Decide whether the camera should refit when the model URL changes.
 * Returns true ONLY when the new URL is non-empty and different from the
 * previous one. Avoids redundant refits on identical re-renders (same URL
 * caused by React state churn) and on unload (newUrl falsy).
 *
 * @param {string | null | undefined} prevUrl
 * @param {string | null | undefined} newUrl
 * @returns {boolean}
 */
export function shouldRefit(prevUrl, newUrl) {
  if (!newUrl) return false;
  return prevUrl !== newUrl;
}

/**
 * Clamp a numeric input from <input type=number>. Returns null for
 * unparseable / out-of-range values so callers can keep last good value.
 *
 * @param {string | number} raw
 * @param {object} [options]
 * @param {number} [options.min=0]
 * @param {number} [options.max=1e6]
 * @returns {number | null}
 */
export function parseDimensionInput(raw, options = {}) {
  const min = options.min ?? 0;
  const max = options.max ?? 1e6;
  if (raw === '' || raw === null || raw === undefined) return null;
  const n = Number(raw);
  if (!Number.isFinite(n)) return null;
  if (n < min || n > max) return null;
  return n;
}
