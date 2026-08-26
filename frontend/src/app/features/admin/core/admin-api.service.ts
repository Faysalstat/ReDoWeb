import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE_URL } from '../../../core/api-config';
import { AdminOverviewResponse } from './admin-api.models';

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
    return this.http.get<AdminOverviewResponse>(`${API_BASE_URL}/api/v1/admin/overview`, {
      params: { days },
    });
  }
}
