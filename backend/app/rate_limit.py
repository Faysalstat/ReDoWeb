from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared Limiter instance -- imported by both main.py (to register it on the
# app + the RateLimitExceeded handler) and individual routers (to decorate
# endpoints), so there's a single source of truth and no circular import.
limiter = Limiter(key_func=get_remote_address)
