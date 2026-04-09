/**
 * LLM / copy-paste sometimes yields literal backslash sequences instead of real newlines.
 * Does not alter normal Unicode newlines already in the string.
 */
export function decodeEscapedLineBreaks(s: string): string {
  const backslash = String.raw`\n`.charAt(0);
  if (!s.includes(backslash)) return s;
  return s
    .replaceAll(String.raw`\r\n`, '\n')
    .replaceAll(String.raw`\n`, '\n')
    .replaceAll(String.raw`\r`, '\n');
}
