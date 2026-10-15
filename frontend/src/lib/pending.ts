// Hands a file picked on the dashboard to the /scan page without a round trip.
let pending: File | null = null;

export function setPendingFile(file: File) {
  pending = file;
}

/** Read without clearing, so a double render in development sees it too. */
export function peekPendingFile(): File | null {
  return pending;
}

export function clearPendingFile() {
  pending = null;
}
