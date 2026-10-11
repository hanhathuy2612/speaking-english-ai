const key = (w: string) => w.toLowerCase().replace(/[^a-z0-9']/g, "");

/** Words of a drill sentence, with its focus words marked (same matching as the backend: case and
 * punctuation ignored). */
export function markFocus(text: string, focus: string[]): { text: string; focus: boolean }[] {
  const keys = new Set(focus.map(key));
  return text.split(/\s+/).filter(Boolean).map((w) => ({ text: w, focus: keys.has(key(w)) }));
}
