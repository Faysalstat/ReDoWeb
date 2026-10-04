import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE_URL } from './api-config';
import {
  BlueprintResponse,
  CrawlResponse,
  DownloadStartResponse,
  DownloadStatusResponse,
  GenerationApprovalResponse,
  GenerationResponse,
  ProjectListItem,
  ProjectStatusResponse,
  ProjectSubmitResponse,
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

  /** Charges the tier's download cost (idempotent per project+tier) and,
   * for a multi-page project without a cached full-site build yet, kicks
   * off one and returns status: "building" instead of "ready". */
  startDownload(projectId: string, tier: string): Observable<DownloadStartResponse> {
    return this.http.post<DownloadStartResponse>(
      `${API_BASE_URL}/api/v1/projects/${projectId}/download?tier=${tier}`,
      {}
    );
  }

  getDownloadStatus(projectId: string, tier: string): Observable<DownloadStatusResponse> {
    return this.http.get<DownloadStatusResponse>(
      `${API_BASE_URL}/api/v1/projects/${projectId}/download-status?tier=${tier}`
    );
  }

  downloadFile(projectId: string, tier: string): Observable<Blob> {
    return this.http.get(`${API_BASE_URL}/api/v1/projects/${projectId}/download-file?tier=${tier}`, {
      responseType: 'blob',
    });
  }
}
