from typing import List, Dict
from collections import defaultdict
from datetime import datetime, timedelta

# In-memory session store — no Redis needed
_sessions: Dict[str, List[Dict]] = {}
_last_seen: Dict[str, datetime] = {}
_rate_counts: Dict[str, int] = {}
_rate_reset: Dict[str, datetime] = {}

MAX_HISTORY = 20
SESSION_TTL_HOURS = 24


def _cleanup():
    cutoff = datetime.utcnow() - timedelta(hours=SESSION_TTL_HOURS)
    stale = [k for k, t in _last_seen.items() if t < cutoff]
    for k in stale:
        _sessions.pop(k, None)
        _last_seen.pop(k, None)


class SessionService:
    async def get_history(self, session_id: str) -> List[Dict]:
        _last_seen[session_id] = datetime.utcnow()
        return list(_sessions.get(session_id, []))

    async def add_turn(self, session_id: str, user_message: str, assistant_message: str):
        history = _sessions.setdefault(session_id, [])
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_message})
        if len(history) > MAX_HISTORY * 2:
            _sessions[session_id] = history[-(MAX_HISTORY * 2):]
        _last_seen[session_id] = datetime.utcnow()
        _cleanup()

    async def clear_session(self, session_id: str):
        _sessions.pop(session_id, None)
        _last_seen.pop(session_id, None)

    async def rate_limit_check(self, api_key_id: str, limit: int) -> tuple[bool, int]:
        now = datetime.utcnow()
        reset_at = _rate_reset.get(api_key_id)
        if reset_at is None or now > reset_at:
            _rate_counts[api_key_id] = 0
            _rate_reset[api_key_id] = now + timedelta(hours=1)
        _rate_counts[api_key_id] = _rate_counts.get(api_key_id, 0) + 1
        count = _rate_counts[api_key_id]
        return count <= limit, max(0, limit - count)


session_service = SessionService()
