import { BadgeVariant } from '../shared/ui/badge/badge.component';

/** Shared mapping from raw backend `Project.status` strings to the UI's
 * 3-stage pipeline (crawl -> extract -> generate). Used by the generation
 * progress page (owns the live polling) and by History (status badge +
 * inline mini progress bar for in-progress rows) so both read the same
 * source of truth instead of duplicating this table. */
export type Stage = 'idle' | 'crawling' | 'extracting' | 'generating' | 'ready' | 'error';

export const STAGE_ORDER: Stage[] = ['crawling', 'extracting', 'generating'];

export const TERMINAL_STATUSES = new Set(['ready', 'failed', 'rejected']);

export const BACKEND_STATUS_TO_STAGE: Record<string, Stage> = {
  pending: 'crawling',
  crawling: 'crawling',
  crawled: 'extracting',
  extracting_blueprint: 'extracting',
  blueprint_ready: 'generating',
  generating: 'generating',
  ready: 'ready',
  failed: 'error',
  rejected: 'error',
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'Queued',
  crawling: 'Crawling',
  crawled: 'Crawling',
  extracting_blueprint: 'Extracting',
  blueprint_ready: 'Generating',
  generating: 'Generating',
  ready: 'Ready',
  failed: 'Failed',
  rejected: 'Rejected',
};

export function stageOf(status: string): Stage {
  return BACKEND_STATUS_TO_STAGE[status] ?? 'crawling';
}

export function isTerminal(status: string): boolean {
  return TERMINAL_STATUSES.has(status);
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

/** Rounded 0-100 progress percentage through the 3-stage pipeline. */
export function stagePercent(status: string): number {
  const stage = stageOf(status);
  const idx = STAGE_ORDER.indexOf(stage);
  if (idx < 0) {
    return stage === 'ready' ? 100 : 0;
  }
  return Math.round(((idx + 1) / STAGE_ORDER.length) * 100);
}

export function statusBadgeVariant(status: string): BadgeVariant {
  if (status === 'ready') {
    return 'success';
  }
  if (status === 'failed' || status === 'rejected') {
    return 'danger';
  }
  return 'accent';
}
