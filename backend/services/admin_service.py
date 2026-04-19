from collections import Counter, deque
from datetime import datetime, timezone
from typing import Any, Dict, List


_RUNTIME_ERRORS: deque[dict[str, Any]] = deque(maxlen=500)


def record_runtime_error(source: str, message: str) -> None:
    _RUNTIME_ERRORS.appendleft(
        {
            "source": str(source or "unknown"),
            "message": str(message or "Unknown error"),
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
    )


def list_recent_runtime_errors(limit: int = 100) -> List[Dict[str, Any]]:
    return list(_RUNTIME_ERRORS)[: max(1, limit)]


def top_runtime_errors(limit: int = 5) -> List[Dict[str, Any]]:
    counter: Counter[tuple[str, str]] = Counter()
    for item in _RUNTIME_ERRORS:
        key = (str(item.get("source", "unknown")), str(item.get("message", "Unknown error")))
        counter[key] += 1

    rows = []
    for (source, message), count in counter.most_common(max(1, limit)):
        rows.append(
            {
                "source": source,
                "message": message,
                "count": int(count),
            }
        )
    return rows
