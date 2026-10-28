// Deployed backend URL (Railway: backend service -> Settings -> Networking).
// No trailing slash. Must be filled in before deploying the frontend.
const DEPLOYED_API_BASE_URL = 'https://redoweb-production.up.railway.app';

// true: `ng serve` on localhost talks to the production backend (real data,
// real credits) instead of a local one on :8123. Production's CORS already
// allows http://localhost:4200. Google sign-in still returns to production's
// REDOWEBS_FRONTEND_URL, so after signing in, change that domain in the address
// bar to http://localhost:4200 (keep the /auth/callback?token=... part).
const USE_PRODUCTION_API_LOCALLY = true;

const LOCAL_HOSTNAMES = ['localhost', '127.0.0.1'];

export const API_BASE_URL =
  LOCAL_HOSTNAMES.includes(window.location.hostname) && !USE_PRODUCTION_API_LOCALLY
    ? 'http://localhost:8123'
    : DEPLOYED_API_BASE_URL;
