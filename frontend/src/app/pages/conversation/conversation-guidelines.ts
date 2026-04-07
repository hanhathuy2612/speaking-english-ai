/** Client cache as JSON array; server/API may use newline-separated text. */
export function parseGuidelineSections(raw: string | undefined): string[] | null {
  if (raw == null || !String(raw).trim()) return null;
  const t = String(raw).trim();
  if (t.startsWith('[')) {
    try {
      const p = JSON.parse(t) as unknown;
      if (Array.isArray(p) && p.every((x) => typeof x === 'string')) return p;
    } catch {
      /* fall through */
    }
  }
  const lines = t.split('\n').filter(Boolean);
  return lines.length ? lines : null;
}

export function stringifyGuidelineSections(sections: string[]): string {
  return JSON.stringify(sections);
}
