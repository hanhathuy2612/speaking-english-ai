import { useCallback, useEffect, useRef } from "react";

/** Keeps recordings as object URLs for "Nghe lại" and frees them when the page unmounts. */
export function useRecordings() {
  const urls = useRef<string[]>([]);
  useEffect(
    () => () => {
      urls.current.forEach((u) => URL.revokeObjectURL(u));
      urls.current = [];
    },
    [],
  );
  return useCallback((blob: Blob) => {
    const url = URL.createObjectURL(blob);
    urls.current.push(url);
    return url;
  }, []);
}
