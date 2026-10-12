// Deployed backend URL (Railway: backend service -> Settings -> Networking).
// No trailing slash. Must be filled in before deploying the frontend.
const DEPLOYED_API_BASE_URL = 'https://redoweb-production.up.railway.app';

const LOCAL_HOSTNAMES = ['localhost', '127.0.0.1'];

export const API_BASE_URL = LOCAL_HOSTNAMES.includes(window.location.hostname)
  ? 'http://localhost:8123'
  : DEPLOYED_API_BASE_URL;
