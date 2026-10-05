import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE_URL } from '../../../core/api-config';
import {
  AdminAdjustmentResponse,
  AdminPaymentsStatusResponse,
  AdminPurchaseActionResponse,
  AdminPurchaseDetailResponse,
  AdminPurchaseListResponse,
  AdminTakeBackResponse,
  AdminTierListResponse,
  AdminTierRow,
  AdminTierUpdateRequest,
  AdminCostByProjectResponse,
  AdminCostByUserResponse,
  AdminCostSettingResponse,
  AdminCostSettingUpdateRequest,
  AdminCreditPackCreateRequest,
  AdminCreditPackListResponse,
  AdminCreditPackRow,
  AdminCreditPackUpdateRequest,
  AdminIssueAdjustmentRequest,
  AdminModelCostResponse,
  AdminModelPricingResponse,
  AdminModelPricingUpdateRequest,
  AdminModelPricingRow,
  AdminOverviewResponse,
  AdminProjectDetailResponse,
  AdminProjectListResponse,
  AdminPromptTemplateListResponse,
  AdminPromptTemplateRow,
  AdminRevenueResponse,
  AdminTierModelListResponse,
  AdminTierModelRow,
  AdminTierModelUpdateRequest,
  AdminUserDetailResponse,
  AdminUserListResponse,
  AdminVisionModelResponse,
  AdminVisionModelUpdateRequest,
} from './admin-api.models';

const ADMIN_BASE = `${API_BASE_URL}/api/v1/admin`;

/** Deliberately kept out of core/redowebs-api.service.ts and scoped to
 * features/admin/ instead: Angular can't tree-shake unused *methods* off a
 * class that's already referenced elsewhere, so bolting a growing admin
 * surface onto the shared service (already injected by every non-admin
 * page) would ship it in every regular user's main bundle for zero benefit.
 * Keeping it here keeps it inside the lazy /admin chunk. */
@Injectable({ providedIn: 'root' })
export class AdminApiService {
  constructor(private readonly http: HttpClient) {}

  getOverview(days: number): Observable<AdminOverviewResponse> {
    return this.http.get<AdminOverviewResponse>(`${ADMIN_BASE}/overview`, { params: { days } });
  }

  // -- Projects -----------------------------------------------------------

  listProjects(params: {
    status?: string;
    tier?: string;
    search?: string;
    userId?: string;
    page?: number;
    pageSize?: number;
  }): Observable<AdminProjectListResponse> {
    const query: Record<string, string | number> = {};
    if (params.status) query['status'] = params.status;
    if (params.tier) query['tier'] = params.tier;
    if (params.search) query['search'] = params.search;
    if (params.userId) query['user_id'] = params.userId;
    query['page'] = params.page ?? 1;
    query['page_size'] = params.pageSize ?? 25;
    return this.http.get<AdminProjectListResponse>(`${ADMIN_BASE}/projects`, { params: query });
  }

  getProjectDetail(projectId: string): Observable<AdminProjectDetailResponse> {
    return this.http.get<AdminProjectDetailResponse>(`${ADMIN_BASE}/projects/${projectId}`);
  }

  // -- Users ----------------------------------------------------------------

  listUsers(params: { search?: string; page?: number; pageSize?: number }): Observable<AdminUserListResponse> {
    const query: Record<string, string | number> = {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 25,
    };
    if (params.search) query['search'] = params.search;
    return this.http.get<AdminUserListResponse>(`${ADMIN_BASE}/users`, { params: query });
  }

  getUserDetail(userId: string): Observable<AdminUserDetailResponse> {
    return this.http.get<AdminUserDetailResponse>(`${ADMIN_BASE}/users/${userId}`);
  }

  issueAdjustment(userId: string, body: AdminIssueAdjustmentRequest): Observable<AdminAdjustmentResponse> {
    return this.http.post<AdminAdjustmentResponse>(`${ADMIN_BASE}/users/${userId}/adjustments`, body);
  }

  // -- Cost / token usage -----------------------------------------------

  getCostByModel(days: number): Observable<AdminModelCostResponse> {
    return this.http.get<AdminModelCostResponse>(`${ADMIN_BASE}/costs/by-model`, { params: { days } });
  }

  getCostByUser(days: number, page = 1, pageSize = 25): Observable<AdminCostByUserResponse> {
    return this.http.get<AdminCostByUserResponse>(`${ADMIN_BASE}/costs/by-user`, {
      params: { days, page, page_size: pageSize },
    });
  }

  getCostByProject(days: number, page = 1, pageSize = 25): Observable<AdminCostByProjectResponse> {
    return this.http.get<AdminCostByProjectResponse>(`${ADMIN_BASE}/costs/by-project`, {
      params: { days, page, page_size: pageSize },
    });
  }

  listModelPricing(): Observable<AdminModelPricingResponse> {
    return this.http.get<AdminModelPricingResponse>(`${ADMIN_BASE}/model-pricing`);
  }

  upsertModelPricing(modelName: string, body: AdminModelPricingUpdateRequest): Observable<AdminModelPricingRow> {
    return this.http.put<AdminModelPricingRow>(
      `${ADMIN_BASE}/model-pricing/${encodeURIComponent(modelName)}`,
      body
    );
  }

  // -- Model config (generation / vision model) --------------------------

  listTierModels(): Observable<AdminTierModelListResponse> {
    return this.http.get<AdminTierModelListResponse>(`${ADMIN_BASE}/model-config/tiers`);
  }

  updateTierModel(key: string, body: AdminTierModelUpdateRequest): Observable<AdminTierModelRow> {
    return this.http.put<AdminTierModelRow>(`${ADMIN_BASE}/model-config/tiers/${key}`, body);
  }

  getVisionModel(): Observable<AdminVisionModelResponse> {
    return this.http.get<AdminVisionModelResponse>(`${ADMIN_BASE}/model-config/vision-model`);
  }

  updateVisionModel(body: AdminVisionModelUpdateRequest): Observable<AdminVisionModelResponse> {
    return this.http.put<AdminVisionModelResponse>(`${ADMIN_BASE}/model-config/vision-model`, body);
  }

  // -- Prompt templates -------------------------------------------------

  listPromptTemplates(): Observable<AdminPromptTemplateListResponse> {
    return this.http.get<AdminPromptTemplateListResponse>(`${ADMIN_BASE}/prompt-templates`);
  }

  uploadPromptTemplate(category: string, name: string, file: File): Observable<AdminPromptTemplateRow> {
    const formData = new FormData();
    formData.append('category', category);
    formData.append('name', name);
    formData.append('file', file);
    return this.http.post<AdminPromptTemplateRow>(`${ADMIN_BASE}/prompt-templates`, formData);
  }

  setPromptTemplateActive(filename: string, isActive: boolean): Observable<AdminPromptTemplateRow> {
    return this.http.patch<AdminPromptTemplateRow>(`${ADMIN_BASE}/prompt-templates/${filename}`, {
      is_active: isActive,
    });
  }

  deletePromptTemplate(filename: string): Observable<void> {
    return this.http.delete<void>(`${ADMIN_BASE}/prompt-templates/${filename}`);
  }

  // -- Cost gate (pre-generation cost estimate + wallet-balance gate) ----
  // See docs/generation-cost-gate-plan.md.

  getCostAlertThreshold(): Observable<AdminCostSettingResponse> {
    return this.http.get<AdminCostSettingResponse>(`${ADMIN_BASE}/cost-gate/threshold`);
  }

  updateCostAlertThreshold(body: AdminCostSettingUpdateRequest): Observable<AdminCostSettingResponse> {
    return this.http.put<AdminCostSettingResponse>(`${ADMIN_BASE}/cost-gate/threshold`, body);
  }

  getUsdPerCredit(): Observable<AdminCostSettingResponse> {
    return this.http.get<AdminCostSettingResponse>(`${ADMIN_BASE}/cost-gate/usd-per-credit`);
  }

  updateUsdPerCredit(body: AdminCostSettingUpdateRequest): Observable<AdminCostSettingResponse> {
    return this.http.put<AdminCostSettingResponse>(`${ADMIN_BASE}/cost-gate/usd-per-credit`, body);
  }

  // -- Earnings -------------------------------------------------------------

  getEarnings(days: number): Observable<AdminRevenueResponse> {
    return this.http.get<AdminRevenueResponse>(`${ADMIN_BASE}/earnings`, { params: { days } });
  }

  // -- Credit packs -----------------------------------------------------------

  listCreditPacks(): Observable<AdminCreditPackListResponse> {
    return this.http.get<AdminCreditPackListResponse>(`${ADMIN_BASE}/credit-packs`);
  }

  createCreditPack(body: AdminCreditPackCreateRequest): Observable<AdminCreditPackRow> {
    return this.http.post<AdminCreditPackRow>(`${ADMIN_BASE}/credit-packs`, body);
  }

  updateCreditPack(id: string, body: AdminCreditPackUpdateRequest): Observable<AdminCreditPackRow> {
    return this.http.put<AdminCreditPackRow>(`${ADMIN_BASE}/credit-packs/${id}`, body);
  }

  setCreditPackActive(id: string, isActive: boolean): Observable<AdminCreditPackRow> {
    return this.http.patch<AdminCreditPackRow>(`${ADMIN_BASE}/credit-packs/${id}/active`, { is_active: isActive });
  }

  // -- Payments ---------------------------------------------------------------

  getPaymentsStatus(): Observable<AdminPaymentsStatusResponse> {
    return this.http.get<AdminPaymentsStatusResponse>(`${ADMIN_BASE}/payments/status`);
  }

  listPurchases(params: {
    status?: string;
    source?: string;
    email?: string;
    includeMock?: boolean;
    page?: number;
    pageSize?: number;
  }): Observable<AdminPurchaseListResponse> {
    const query: Record<string, string | number | boolean> = {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 25,
      include_mock: params.includeMock ?? false,
    };
    if (params.status) query['status'] = params.status;
    if (params.source) query['source'] = params.source;
    if (params.email) query['email'] = params.email;
    return this.http.get<AdminPurchaseListResponse>(`${ADMIN_BASE}/purchases`, { params: query });
  }

  getPurchase(id: string): Observable<AdminPurchaseDetailResponse> {
    return this.http.get<AdminPurchaseDetailResponse>(`${ADMIN_BASE}/purchases/${id}`);
  }

  recheckPurchase(id: string): Observable<AdminPurchaseActionResponse> {
    return this.http.post<AdminPurchaseActionResponse>(`${ADMIN_BASE}/purchases/${id}/recheck`, {});
  }

  takeBackCredits(id: string, note: string): Observable<AdminTakeBackResponse> {
    return this.http.post<AdminTakeBackResponse>(`${ADMIN_BASE}/purchases/${id}/take-back`, { note });
  }

  markPurchaseFailed(id: string, note: string): Observable<AdminPurchaseActionResponse> {
    return this.http.post<AdminPurchaseActionResponse>(`${ADMIN_BASE}/purchases/${id}/mark-failed`, { note });
  }

  // -- Tiers & pricing ----------------------------------------------------------

  listTiers(): Observable<AdminTierListResponse> {
    return this.http.get<AdminTierListResponse>(`${ADMIN_BASE}/tiers`);
  }

  updateTier(key: string, body: AdminTierUpdateRequest): Observable<AdminTierRow> {
    return this.http.put<AdminTierRow>(`${ADMIN_BASE}/tiers/${key}`, body);
  }

  setTierActive(key: string, isActive: boolean): Observable<AdminTierRow> {
    return this.http.patch<AdminTierRow>(`${ADMIN_BASE}/tiers/${key}/active`, { is_active: isActive });
  }
}
