import { describe, it, expect } from 'vitest';
import {
  computeAutoRotateSpeed,
  shouldRefit,
  parseDimensionInput,
} from './viewerControls.js';

describe('computeAutoRotateSpeed', () => {
  it('returns base speed when bbox is missing', () => {
    expect(computeAutoRotateSpeed(null)).toBe(1.4);
    expect(computeAutoRotateSpeed(undefined)).toBe(1.4);
    expect(computeAutoRotateSpeed({})).toBe(1.4);
  });

  it('returns base speed when bbox.size is malformed', () => {
    expect(computeAutoRotateSpeed({ size: [] })).toBe(1.4);
    expect(computeAutoRotateSpeed({ size: [10, 10] })).toBe(1.4); // length < 3
    expect(computeAutoRotateSpeed({ size: [0, 0, 0] })).toBe(1.4);
  });

  it('returns base speed at the 30 mm reference part', () => {
    // 30 mm reference (M8x30 hex bolt) → ratio=1 → cbrt=1 → base unchanged.
    const speed = computeAutoRotateSpeed({ size: [13, 13, 30] });
    expect(speed).toBeCloseTo(1.4, 5);
  });

  it('rotates faster for tiny parts but never above maxSpeed', () => {
    const tiny = computeAutoRotateSpeed({ size: [3, 3, 4] }); // M2 washer-ish
    expect(tiny).toBeGreaterThan(1.4);
    expect(tiny).toBeLessThanOrEqual(1.6);
  });

  it('rotates slower for large parts but never below minSpeed', () => {
    const large = computeAutoRotateSpeed({ size: [40, 40, 200] }); // M20×200
    expect(large).toBeLessThan(1.4);
    expect(large).toBeGreaterThanOrEqual(0.4);
  });

  it('clamps strictly to the configured min/max bounds', () => {
    const huge = computeAutoRotateSpeed({ size: [9999, 9999, 9999] });
    expect(huge).toBe(0.4);
    const microscopic = computeAutoRotateSpeed({ size: [0.001, 0.001, 0.001] });
    expect(microscopic).toBe(1.6);
  });

  it('honours custom base/min/max overrides', () => {
    const speed = computeAutoRotateSpeed({ size: [13, 13, 30] }, { base: 2.0, maxSpeed: 3.0 });
    expect(speed).toBeCloseTo(2.0, 5);
  });
});

describe('shouldRefit', () => {
  it('refits when URL changes to a non-empty value', () => {
    expect(shouldRefit('a.glb', 'b.glb')).toBe(true);
    expect(shouldRefit(null, 'b.glb')).toBe(true);
    expect(shouldRefit(undefined, 'b.glb')).toBe(true);
  });

  it('does NOT refit when the URL is unchanged (avoids redundant camera moves)', () => {
    expect(shouldRefit('a.glb', 'a.glb')).toBe(false);
  });

  it('does NOT refit when the new URL is empty (model unloaded)', () => {
    expect(shouldRefit('a.glb', null)).toBe(false);
    expect(shouldRefit('a.glb', undefined)).toBe(false);
    expect(shouldRefit('a.glb', '')).toBe(false);
  });
});

describe('parseDimensionInput', () => {
  it('parses valid numeric strings within range', () => {
    expect(parseDimensionInput('12.5')).toBe(12.5);
    expect(parseDimensionInput(8)).toBe(8);
    expect(parseDimensionInput('0')).toBe(0);
  });

  it('returns null for empty / null / undefined', () => {
    expect(parseDimensionInput('')).toBeNull();
    expect(parseDimensionInput(null)).toBeNull();
    expect(parseDimensionInput(undefined)).toBeNull();
  });

  it('returns null for non-numeric strings (NaN guard)', () => {
    expect(parseDimensionInput('abc')).toBeNull();
    expect(parseDimensionInput('1,5')).toBeNull(); // comma — locale issue
  });

  it('respects min/max bounds, returning null outside range', () => {
    expect(parseDimensionInput('5', { min: 10 })).toBeNull();
    expect(parseDimensionInput('100', { max: 50 })).toBeNull();
    expect(parseDimensionInput('25', { min: 10, max: 50 })).toBe(25);
  });

  it('rejects negative diameters by default (min defaults to 0)', () => {
    expect(parseDimensionInput('-5')).toBeNull();
  });
});
