import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE_URL } from './api-config';
import {
  BillingConfigResponse,
  BlueprintResponse,
  CaptureResponse,
  CreateOrderResponse,
  CreditPackListResponse,
  CrawlResponse,
  ActionStartResponse,
  GenerationApprovalResponse,
  GenerationResponse,
  ProjectListItem,
  ProjectStatusResponse,
  ProjectSubmitResponse,
  PublicTierListResponse,
  PurchaseHistoryResponse,
  PurchaseResponse,
  TierRetryResponse,
  WalletResponse,
} from './redowebs-api.models';

@Injectable({ providedIn: 'root' })
export class RedoWebsApiService {
  constructor(private readonly http: HttpClient) {}

  /** @deprecated superseded by submitProject() -- kept for backend debugging only. */
  crawl(url: string, tosAccepted: boolean): Observable<CrawlResponse> {
    return this.http.post<CrawlResponse>(`${API_BASE_URL}/api/v1/crawl`, {
      url,
      tos_accepted: tosAccepted,
    });
  }

  /** @deprecated superseded by submitProject() -- kept for backend debugging only. */
  extractBlueprint(projectId: string): Observable<BlueprintResponse> {
    return this.http.post<BlueprintResponse>(
      `${API_BASE_URL}/api/v1/projects/${projectId}/blueprint`,
      {}
    );
  }

  /** @deprecated superseded by submitProject() -- kept for backend debugging only. */
  generate(projectId: string, tier: string): Observable<GenerationResponse> {
    return this.http.post<GenerationResponse>(
      `${API_BASE_URL}/api/v1/projects/${projectId}/generate?tier=${tier}`,
      {}
    );
  }

  /** Kicks off the full crawl -> blueprint -> generate Celery chain and
   * returns immediately with a project id to poll. */
  submitProject(url: string, tosAccepted: boolean): Observable<ProjectSubmitResponse> {
    return this.http.post<ProjectSubmitResponse>(`${API_BASE_URL}/api/v1/projects`, {
      url,
      tos_accepted: tosAccepted,
    });
  }

  getProjectStatus(projectId: string): Observable<ProjectStatusResponse> {
    return this.http.get<ProjectStatusResponse>(`${API_BASE_URL}/api/v1/projects/${projectId}`);
  }

  /** Re-runs one failed tier against the blueprint already on disk -- no
   * re-crawl and no extra credits. Other tiers' finished output is
   * untouched. */
  retryTier(projectId: string, tier: string): Observable<TierRetryResponse> {
    return this.http.post<TierRetryResponse>(
      `${API_BASE_URL}/api/v1/projects/${projectId}/retry-tier?tier=${encodeURIComponent(tier)}`,
      {}
    );
  }

  /** User's response to the awaiting_cost_approval gate (see
   * docs/generation-cost-gate-plan.md) -- a 200 with approved: false on
   * insufficient balance is a normal outcome, not an error. */
  approveGeneration(projectId: string): Observable<GenerationApprovalResponse> {
    return this.http.post<GenerationApprovalResponse>(
      `${API_BASE_URL}/api/v1/projects/${projectId}/approve-generation`,
      {}
    );
  }

  listProjects(): Observable<ProjectListItem[]> {
    return this.http.get<ProjectListItem[]>(`${API_BASE_URL}/api/v1/projects`);
  }

  getWallet(): Observable<WalletResponse> {
    return this.http.get<WalletResponse>(`${API_BASE_URL}/api/v1/credits/wallet`);
  }

  /** Buys a tier's design (charges its credit cost once per project+tier;
   * buying again is free). Unlocks Download, Generate all pages and, on
   * Pro/Premium, Run SEO. Starts nothing by itself. */
  purchaseTier(projectId: string, tier: string): Observable<PurchaseResponse> {
    return this.http.post<PurchaseResponse>(
      `${API_BASE_URL}/api/v1/projects/${projectId}/purchase?tier=${encodeURIComponent(tier)}`,
      {}
    );
  }

  /** "Generate all pages" -- builds the rest of a multi-page site in the
   * preview's design. Purchase required; once per purchase. */
  startFullSite(projectId: string, tier: string): Observable<ActionStartResponse> {
    return this.http.post<ActionStartResponse>(
      `${API_BASE_URL}/api/v1/projects/${projectId}/full-site?tier=${encodeURIComponent(tier)}`,
      {}
    );
  }

  /** "Run SEO agent" (Pro/Premium) -- on a multi-page site only after all
   * pages are generated. Purchase required; once per purchase. */
  startSeo(projectId: string, tier: string): Observable<ActionStartResponse> {
    return this.http.post<ActionStartResponse>(
      `${API_BASE_URL}/api/v1/projects/${projectId}/seo?tier=${encodeURIComponent(tier)}`,
      {}
    );
  }

  /** The best finished output right now (SEO version, then all pages, then
   * the home-page preview). Purchase required. */
  downloadFile(projectId: string, tier: string): Observable<Blob> {
    return this.http.get(`${API_BASE_URL}/api/v1/projects/${projectId}/download-file?tier=${tier}`, {
      responseType: 'blob',
    });
  }

  /** Public -- enabled tiers with their download credit cost. */
  getTiers(): Observable<PublicTierListResponse> {
    return this.http.get<PublicTierListResponse>(`${API_BASE_URL}/api/v1/tiers`);
  }

  /** Public -- PayPal client id/env for loading the JS SDK. */
  getBillingConfig(): Observable<BillingConfigResponse> {
    return this.http.get<BillingConfigResponse>(`${API_BASE_URL}/api/v1/billing/config`);
  }

  /** Public -- active credit packs, cheapest-first by admin sort order. */
  getCreditPacks(): Observable<CreditPackListResponse> {
    return this.http.get<CreditPackListResponse>(`${API_BASE_URL}/api/v1/billing/credit-packs`);
  }

  /** Creates the PayPal order for a pack. The price is decided server-side
   * from the pack, never sent from here. */
  createPayPalOrder(packId: string): Observable<CreateOrderResponse> {
    return this.http.post<CreateOrderResponse>(`${API_BASE_URL}/api/v1/billing/paypal/orders`, {
      pack_id: packId,
    });
  }

  /** Called from the PayPal button's onApprove -- captures the payment and
   * credits the wallet (exactly once, even if the webhook also fires). */
  capturePayPalOrder(orderId: string): Observable<CaptureResponse> {
    return this.http.post<CaptureResponse>(
      `${API_BASE_URL}/api/v1/billing/paypal/orders/${encodeURIComponent(orderId)}/capture`,
      {}
    );
  }

  listPurchases(): Observable<PurchaseHistoryResponse> {
    return this.http.get<PurchaseHistoryResponse>(`${API_BASE_URL}/api/v1/billing/purchases`);
  }
}
