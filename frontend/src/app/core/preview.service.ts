import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import { API_BASE_URL } from './api-config';
import { PreviewTokenResponse } from './redowebs-api.models';

/** Mints a short-lived preview token and builds the full, directly-loadable
 * preview URL for a generated site. Lives in `core/` (not `features/admin/`)
 * because both the regular user's own in-progress/finished generation
 * preview (GenerationProgressComponent) and the admin dashboard's
 * cross-user preview viewer need it -- the backend's
 * POST /projects/{id}/preview-token endpoint allows both the project owner
 * and an admin.
 *
 * An <iframe src> can't carry an Authorization header, so the token travels
 * in the query string instead: mint it via one authenticated POST, then
 * append it to the pre-built preview_url_path the status/detail endpoints
 * already return. */
@Injectable({ providedIn: 'root' })
export class PreviewService {
  constructor(private readonly http: HttpClient) {}

  getAuthedPreviewUrl(projectId: string, previewUrlPath: string): Observable<string> {
    return this.http
      .post<PreviewTokenResponse>(`${API_BASE_URL}/api/v1/projects/${projectId}/preview-token`, {})
      .pipe(
        map(
          (res) =>
            `${API_BASE_URL}${previewUrlPath}?preview_token=${encodeURIComponent(res.preview_token)}`
        )
      );
  }
}
