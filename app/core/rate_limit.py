"""Shared slowapi Limiter.

Keyed by remote address. Applied selectively (via ``@limiter.limit(...)`` on
individual routes) to the two endpoints that trigger real work — incident
creation and analysis kickoff — rather than globally, so read-only traffic
isn't throttled by the same budget as expensive writes.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
