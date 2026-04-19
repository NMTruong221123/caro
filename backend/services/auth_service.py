from typing import Any, Dict, Optional

from werkzeug.security import check_password_hash, generate_password_hash

from backend.services import db_service


def sanitize_user(user: Dict[str, Any]) -> Dict[str, Any]:
    tier, stars, streak = db_service.normalize_rank_state(
        str(user.get("rank_tier", "Bronze")),
        int(user.get("rank_stars", 0)),
        int(user.get("rank_streak", 0)),
    )
    rank_visual = db_service.rank_badge_info(tier, stars)
    selected_title_code = str(user.get("selected_title_code", ""))
    selected_title_name = db_service.get_selected_title_name(int(user.get("id", 0)), selected_title_code)

    return {
        "id": user["id"],
        "username": user["username"],
        "isAdmin": bool(int(user.get("is_admin", 0))),
        "rating": user.get("rating", 1000),
        "wins": user.get("wins", 0),
        "losses": user.get("losses", 0),
        "draws": user.get("draws", 0),
        "gamesPlayed": user.get("games_played", 0),
        "winsVsAi": user.get("wins_vs_ai", 0),
        "winsVsRoom": user.get("wins_vs_room", 0),
        "winsRanked": user.get("wins_ranked", 0),
        "rankPoints": user.get("rank_points", 0),
        "rankTier": tier,
        "rankStars": stars,
        "rankStreak": streak,
        "gamesVsAi": user.get("games_vs_ai", 0),
        "gamesVsRoom": user.get("games_vs_room", 0),
        "gamesRanked": user.get("games_ranked", 0),
        "avatar": user.get("avatar", "🙂"),
        "selectedTitleCode": selected_title_code,
        "selectedTitleName": selected_title_name,
        "selectedFrameCode": user.get("selected_frame_code", ""),
        "rankVisual": rank_visual,
    }


def register_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    password_hash = generate_password_hash(password)
    user_id = db_service.create_user(username, password_hash)
    if user_id is None:
        return None
    created = db_service.get_user_by_id(user_id)
    if not created:
        return None
    return sanitize_user(created)


def login_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    user = db_service.get_user_by_username(username)
    if not user:
        return None

    if not check_password_hash(user["password_hash"], password):
        return None

    token = db_service.create_session(user["id"])
    return {
        "token": token,
        "user": sanitize_user(user),
    }


def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    user = db_service.get_user_by_token(token)
    if not user:
        return None
    return sanitize_user(user)
