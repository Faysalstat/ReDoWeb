export interface PageRecord {
  url: string;
  http_status: number;
  storage_path: string;
}

export interface AssetRecord {
  original_url: string;
  asset_type: string;
  storage_path: string;
  content_type?: string | null;
}

export interface CrawlResponse {
  project_id: string;
  source_url: string;
  page_count: number;
  pages: PageRecord[];
  assets: AssetRecord[];
}

export interface ColorPalette {
  primary: string;
  secondary: string;
  accent: string;
}

export interface Fonts {
  heading: string;
  body: string;
}

export interface Frontmatter {
  site_name: string;
  colors: ColorPalette;
  logo?: string | null;
  fonts: Fonts;
  tone?: string | null;
}

export interface BlueprintResponse {
  project_id: string;
  design_md_path: string;
  frontmatter: Frontmatter;
  design_md: string;
}

export interface PostprocessReport {
  alt_text_added: string[];
  og_tags_added: string[];
  contrast_warnings: string[];
  sitemap_written: boolean;
}

export interface GenerationUsage {
  prompt_tokens: number;
  completion_tokens: number;
}

export interface GenerationResponse {
  project_id: string;
  tier: string;
  postprocess: PostprocessReport;
  template_used: string;
  output_dir: string;
  files: string[];
  summary: string;
  usage: GenerationUsage;
  iterations: number;
}

// --- Async job (Celery-backed) submission + polling ---

export interface ProjectSubmitResponse {
  project_id: string;
  status: string;
}

export interface ProjectBlueprintSummary {
  site_name?: string | null;
  colors?: ColorPalette | null;
  fonts?: Fonts | null;
  tone?: string | null;
}

export interface ProjectGenerationSummary {
  tier: string;
  template_used: string;
  preview_url_path: string;
  summary?: string | null;
  contrast_warnings: string[];
}

export interface ProjectStatusResponse {
  project_id: string;
  status: string;
  rejection_reason?: string | null;
  source_url: string;
  blueprint?: ProjectBlueprintSummary | null;
  /** One entry per tier that has finished generating so far -- populated
   * progressively, not only once the whole project is "ready". */
  generations: ProjectGenerationSummary[];
  tiers_total: number;
  tiers_completed: number;
  /** Tiers now fan out and generate independently, so more than one can be
   * "running" at once -- plural, not just the tail of a chain. */
  current_tiers: string[];
}

export interface ProjectListItem {
  project_id: string;
  source_url: string;
  status: string;
  created_at: string;
  tier?: string | null;
}

// --- Auth (Google SSO) ---

export interface UserOut {
  id: string;
  email: string;
  is_admin: boolean;
}

export interface WalletResponse {
  balance: number;
}

// --- Preview (authed, owner-or-admin) ---

export interface PreviewTokenResponse {
  preview_token: string;
  expires_in: number;
}

// --- Downloads (lazy full-site build on purchase) ---

export interface DownloadStartResponse {
  status: 'ready' | 'building';
  project_id: string;
  tier: string;
  job_id?: string | null;
}

export interface DownloadStatusResponse {
  status: 'ready' | 'building' | 'failed';
  failure_reason?: string | null;
}
