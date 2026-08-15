"""Shared rate limiter for the API (slowapi, keyed on client IP)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

AUTH_RATE_LIMIT = "5/minute"

limiter = Limiter(key_func=get_remote_address)
