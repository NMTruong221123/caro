from typing import Any, Dict, Tuple

from config.settings import ADMIN_DASHBOARD_TOKEN, CHAT_BANNED_WORDS
from backend.services import auth_service
from backend.services import admin_service, db_service, online_service
from backend.services.socket_service import get_connected_stats


def _authorized(token: str, user_token: str = "") -> bool:
    expected = str(ADMIN_DASHBOARD_TOKEN or "").strip()
    provided = str(token or "").strip()
    if bool(expected) and provided == expected:
        return True

    if user_token:
        user = auth_service.get_user_from_token(user_token)
        if user and (bool(user.get("isAdmin")) or str(user.get("username", "")).upper() == "ADMIN"):
            return True
    return False


def dashboard_summary(admin_token: str, user_token: str = "") -> Tuple[Dict[str, Any], int]:
    if not _authorized(admin_token, user_token=user_token):
        return {"error": "Admin token khong hop le"}, 401

    active_rooms = db_service.list_active_rooms(limit=20)
    connected = get_connected_stats()
    queue_stats = online_service.get_rank_queue_stats()
    security_events = online_service.list_recent_rank_security_events(limit=30)
    top_errors = admin_service.top_runtime_errors(limit=8)

    return {
        "stats": {
            "activeRooms": len(active_rooms),
            "onlineUsers": int(connected.get("onlineUsers", 0)),
            "openSockets": int(connected.get("openSockets", 0)),
            "rankQueueSize": int(queue_stats.get("queueSize", 0)),
        },
        "activeRooms": active_rooms,
        "rankQueue": queue_stats,
        "securityEvents": security_events,
        "topErrors": top_errors,
        "chatFilter": {
            "defaultBannedWords": [str(item) for item in CHAT_BANNED_WORDS],
            "customBannedWords": db_service.get_custom_banned_words(),
        },
    }, 200


def update_chat_filter(admin_token: str, payload: Dict[str, Any], user_token: str = "") -> Tuple[Dict[str, Any], int]:
    if not _authorized(admin_token, user_token=user_token):
        return {"error": "Admin token khong hop le"}, 401

    raw_words = payload.get("customBannedWords", [])
    if isinstance(raw_words, str):
        raw_words = [item.strip() for item in raw_words.replace(",", "\n").split("\n") if item.strip()]
    if not isinstance(raw_words, list):
        return {"error": "customBannedWords khong hop le"}, 400

    words: list[str] = []
    for item in raw_words:
        word = str(item).strip().lower()
        if not word:
            continue
        if len(word) > 24:
            return {"error": "Moi tu cam toi da 24 ky tu"}, 400
        words.append(word)

    if len(words) > 200:
        return {"error": "Toi da 200 tu cam tuy chinh"}, 400

    saved = db_service.set_custom_banned_words(words)
    online_service.refresh_custom_banned_cache()
    return {"customBannedWords": saved}, 200
