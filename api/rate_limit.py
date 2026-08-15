"""Shared rate limiter for the API (slowapi, keyed on client IP)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

AUTH_RATE_LIMIT = "5/minute"

# Persistent, per-(ip, email) daily cap enforced via services.database.record_auth_attempt.
# Deliberately looser than AUTH_RATE_LIMIT's per-minute burst cap and restart-safe (DB-backed,
# not in-memory) — it catches slow credential-stuffing that stays under the burst threshold.
AUTH_MAX_ATTEMPTS_PER_DAY = 20

limiter = Limiter(key_func=get_remote_address)
