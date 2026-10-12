import { BadgeVariant } from '../core/project-status';

/** Maps a status tone (core/project-status.ts) to its `.pg-chip` modifier. */
const CHIP_CLASS: Record<BadgeVariant, string> = {
  accent: 'pg-chip pg-chip--accent',
  muted: 'pg-chip',
  warning: 'pg-chip pg-chip--amber',
  success: 'pg-chip pg-chip--mint',
  danger: 'pg-chip pg-chip--danger',
};

export function chipClass(variant: BadgeVariant): string {
  return CHIP_CLASS[variant] ?? 'pg-chip';
}
