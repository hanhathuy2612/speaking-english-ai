/** Pure helpers of the admin content editor (features/admin/UnitEditor.tsx). */

/** Unit id from its English title: lower-case words joined by "-" (the backend's ID_RE). */
export function slugify(title: string): string {
  return title
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // accents
    .replace(/đ/g, "d")
    .replace(/'/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40)
    .replace(/-+$/, "");
}

/** "a, b ,, c" -> ["a", "b", "c"] (phrase cues, `when` cues). */
export const splitList = (text: string): string[] =>
  text
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

/** Move item i by `step` places (-1 up, 1 down); out of range leaves the list as is. */
export function moved<T>(items: T[], i: number, step: number): T[] {
  const j = i + step;
  if (j < 0 || j >= items.length) return items;
  const out = [...items];
  [out[i], out[j]] = [out[j], out[i]];
  return out;
}

/** After phrase `removed` is deleted, questions and lesson sentences point to the right phrases again. */
export function shiftPhrase(index: number, removed: number): number | null {
  if (index === removed) return null;
  return index > removed ? index - 1 : index;
}
