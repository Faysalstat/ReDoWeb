import { BadgeVariant } from '../shared/ui/badge/badge.component';

/** Shared mapping from raw backend `Project.status` strings to the UI's
 * 3-stage pipeline (crawl -> extract -> generate). Used by the generation
 * progress page (owns the live polling) and by History (status badge +
 * inline mini progress bar for in-progress rows) so both read the same
 * source of truth instead of duplicating this table. */
export type Stage =
  | 'idle'
  | 'crawling'
  | 'extracting'
  | 'generating'
  | 'awaiting_approval'
  | 'ready'
  | 'error';

export const STAGE_ORDER: Stage[] = ['crawling', 'extracting', 'generating'];

export const TERMINAL_STATUSES = new Set(['ready', 'failed', 'rejected']);

export const BACKEND_STATUS_TO_STAGE: Record<string, Stage> = {
  pending: 'crawling',
  crawling: 'crawling',
  crawled: 'extracting',
  extracting_blueprint: 'extracting',
  blueprint_ready: 'generating',
  generating: 'generating',
  // Not terminal -- polling keeps running so the UI can react once the user
  // approves or tops up (see docs/generation-cost-gate-plan.md).
  awaiting_cost_approval: 'awaiting_approval',
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
  awaiting_cost_approval: 'Awaiting approval',
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
  if (stage === 'ready') {
    return 100;
  }
  if (stage === 'awaiting_approval') {
    // Paused between "extracting" and "generating" -- show progress as
    // extracting-just-finished rather than resetting to 0%.
    return Math.round(((STAGE_ORDER.indexOf('extracting') + 1) / STAGE_ORDER.length) * 100);
  }
  const idx = STAGE_ORDER.indexOf(stage);
  return idx < 0 ? 0 : Math.round(((idx + 1) / STAGE_ORDER.length) * 100);
}

/** Display label for a tier key ("premium" -> "Premium"). Tier keys are
 * admin-managed free text in the `tiers` table, so this is a display-only
 * fallback, not a lookup against a fixed enum. */
export function tierLabel(key: string): string {
  return key.length > 0 ? key.charAt(0).toUpperCase() + key.slice(1) : key;
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
