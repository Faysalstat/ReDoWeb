// Literal class sets so Tailwind's scanner sees every one. Never build these
// with string concatenation ('text-' + c + '-400' produces no CSS).
export type Accent = 'cyan' | 'purple' | 'blue' | 'orange' | 'green' | 'pink' | 'yellow' | 'red';

export const ACCENTS: Record<Accent, { icon: string; tile: string; border: string; hoverBorder: string; soft: string }> = {
  cyan:   { icon: 'text-cyan-400',   tile: 'bg-cyan-500/10',   border: 'border-cyan-500/20',   hoverBorder: 'hover:border-cyan-500/40',   soft: 'bg-cyan-500/5' },
  purple: { icon: 'text-purple-400', tile: 'bg-purple-500/10', border: 'border-purple-500/20', hoverBorder: 'hover:border-purple-500/40', soft: 'bg-purple-500/5' },
  blue:   { icon: 'text-blue-400',   tile: 'bg-blue-500/10',   border: 'border-blue-500/20',   hoverBorder: 'hover:border-blue-500/40',   soft: 'bg-blue-500/5' },
  orange: { icon: 'text-orange-400', tile: 'bg-orange-500/10', border: 'border-orange-500/20', hoverBorder: 'hover:border-orange-500/40', soft: 'bg-orange-500/5' },
  green:  { icon: 'text-green-400',  tile: 'bg-green-500/10',  border: 'border-green-500/20',  hoverBorder: 'hover:border-green-500/40',  soft: 'bg-green-500/5' },
  pink:   { icon: 'text-pink-400',   tile: 'bg-pink-500/10',   border: 'border-pink-500/20',   hoverBorder: 'hover:border-pink-500/40',   soft: 'bg-pink-500/5' },
  yellow: { icon: 'text-yellow-400', tile: 'bg-yellow-500/10', border: 'border-yellow-500/20', hoverBorder: 'hover:border-yellow-500/40', soft: 'bg-yellow-500/5' },
  red:    { icon: 'text-red-400',    tile: 'bg-red-500/10',    border: 'border-red-500/20',    hoverBorder: 'hover:border-red-500/40',    soft: 'bg-red-500/5' },
};

/** Pill colors keyed by the raw backend Project.status (see core/project-status.ts). */
export const STATUS_PILL: Record<string, string> = {
  pending: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  crawling: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  crawled: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  extracting_blueprint: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  blueprint_ready: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  generating: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  awaiting_cost_approval: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  ready: 'bg-green-500/10 text-green-400 border-green-500/20',
  failed: 'bg-red-500/10 text-red-400 border-red-500/20',
  rejected: 'bg-red-500/10 text-red-400 border-red-500/20',
};

/** Statuses that show a spinner in their pill. */
export const BUSY_STATUSES = new Set([
  'pending',
  'crawling',
  'crawled',
  'extracting_blueprint',
  'blueprint_ready',
  'generating',
]);
