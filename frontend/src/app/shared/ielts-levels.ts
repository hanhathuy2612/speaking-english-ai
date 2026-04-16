/** IELTS Speaking target bands (matches backend app.core.ielts_levels). */

export const IELTS_SPEAKING_BAND_VALUES = [
  '4',
  '4.5',
  '5',
  '5.5',
  '6',
  '6.5',
  '7',
  '7.5',
  '8',
  '8.5',
  '9',
] as const;

const BAND_NUMS = new Set(IELTS_SPEAKING_BAND_VALUES.map(Number));

const LEGACY_CEFR_TO_BAND: Record<string, string> = {
  a1: '4',
  a2: '5',
  b1: '6',
  b2: '6.5',
  c1: '7.5',
};

export type IeltsBadgeTier = 'none' | 'low' | 'mid' | 'strong' | 'expert';

/** Parse a valid IELTS band; returns null if unknown. */
export function parseIeltsBand(raw: string | null | undefined): number | null {
  if (raw == null) return null;
  const s = String(raw).trim().replace(',', '.');
  if (!s) return null;
  const n = Number(s);
  if (!Number.isFinite(n)) return null;
  const snapped = Math.round(n * 2) / 2;
  if (!BAND_NUMS.has(snapped)) return null;
  return snapped;
}

/** Resolve IELTS band or legacy CEFR topic label (for prompts / badges). */
export function resolveIeltsBand(raw: string | null | undefined): number | null {
  const direct = parseIeltsBand(raw);
  if (direct != null) return direct;
  if (raw == null) return null;
  const key = String(raw).trim().toLowerCase();
  if (!key) return null;
  const mapped = LEGACY_CEFR_TO_BAND[key];
  return mapped == null ? null : parseIeltsBand(mapped);
}

export function formatIeltsBand(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

/** Normalize free text to a canonical band string when possible. */
export function normalizeIeltsLevelInput(raw: string | null | undefined): string {
  const n = resolveIeltsBand(raw);
  return n == null ? (raw ?? '').trim() : formatIeltsBand(n);
}

export function ieltsBadgeTier(level: string | null | undefined): IeltsBadgeTier {
  const n = resolveIeltsBand(level);
  if (n == null) return 'none';
  if (n <= 5) return 'low';
  if (n <= 6) return 'mid';
  if (n <= 7.5) return 'strong';
  return 'expert';
}
