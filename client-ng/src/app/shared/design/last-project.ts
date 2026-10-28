// The last project submitted from this browser, for the navbar's
// "View My Redesign" link. A per-browser convenience only: storage can be
// blocked or cleared, so every access is wrapped and failures are ignored.
const KEY = 'redowebs_last_project_id';

export function readLastProjectId(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function rememberLastProjectId(projectId: string): void {
  try {
    localStorage.setItem(KEY, projectId);
  } catch {
    // storage unavailable; the link just won't show
  }
}
