import { Injectable, signal } from '@angular/core';
import { Observable, of, timer } from 'rxjs';
import { map } from 'rxjs/operators';
import { ADMIN, FINDINGS, INVOICES, PHASES, PLANS, PLAN_MATRIX, PREVIEW_SCORES, SITES } from './mock-data';
import { AdminOverview, Finding, Invoice, Plan, PreviewScores, Scan, ScanPhase, Site } from './models';

/**
 * Every method below returns an Observable of the shape the UI renders, backed
 * by mock data. To go live, replace each body with the HttpClient call named in
 * its TODO — no template or component change is needed.
 */
@Injectable({ providedIn: 'root' })
export class RefitService {
  /** The URL typed on the landing page, carried into the scan route. */
  readonly lastUrl = signal<string>('');

  /** TODO: POST /api/scans { url } → { id } */
  startScan(url: string): Observable<{ id: string }> {
    this.lastUrl.set(url);
    return of({ id: 'sc_' + Math.random().toString(36).slice(2, 8) });
  }

  /**
   * TODO: GET /api/scans/:id — poll every 2s, or subscribe to
   * SSE /api/scans/:id/events for phase + finding updates.
   * The mock advances one percent a second and reveals findings as it goes.
   */
  scan(id: string): Observable<Scan> {
    const url = this.lastUrl() || 'brightwood-dental.com';
    return timer(0, 900).pipe(
      map((tick) => {
        const percent = Math.min(99, 12 + tick);
        const phaseIndex = percent < 20 ? 0 : percent < 40 ? 1 : percent < 75 ? 2 : percent < 92 ? 3 : 4;
        const phases: ScanPhase[] = PHASES.map((p, i) => ({
          ...p,
          state: i < phaseIndex ? 'done' : i === phaseIndex ? 'running' : 'waiting',
          detail: i === phaseIndex ? percent + '%' : undefined,
        }));
        const findings: Finding[] = FINDINGS.slice(0, Math.max(1, Math.round(percent / 16)));
        return {
          id, url, percent, phaseIndex, phases, findings,
          etaMinutes: Math.max(1, Math.round((100 - percent) * 0.06)),
        };
      }),
    );
  }

  /** TODO: GET /api/previews/:id */
  previewScores(_id: string): Observable<PreviewScores> {
    return of(PREVIEW_SCORES);
  }

  /** TODO: GET /api/previews/:id/pages */
  previewPages(_id: string): Observable<string[]> {
    return of(['Home', 'Services', 'Team', 'Contact']);
  }

  /** TODO: GET /api/plans */
  plans(): Observable<Plan[]> {
    return of(PLANS);
  }

  planMatrix(): Observable<typeof PLAN_MATRIX> {
    return of(PLAN_MATRIX);
  }

  /** TODO: GET /api/sites */
  sites(): Observable<Site[]> {
    return of(SITES);
  }

  /** TODO: GET /api/billing/invoices */
  invoices(): Observable<Invoice[]> {
    return of(INVOICES);
  }

  /** TODO: POST /api/checkout { planId, paymentMethod } */
  pay(planId: string): Observable<{ ok: true; planId: string }> {
    return of({ ok: true as const, planId });
  }

  /** TODO: GET /api/admin/overview */
  adminOverview(): Observable<AdminOverview> {
    return of(ADMIN);
  }
}
