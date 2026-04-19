from typing import Any, Dict, Tuple

from backend.services import auth_service, db_service, game_service, online_service


def _sync_achievements_for_user(user_id: int, wins: int, games: int, tier: str) -> None:
    threshold = 12
    level = 1
    while threshold <= 1536:
        db_service.upsert_user_achievement(
            user_id,
            code=f"wins_{threshold}",
            title=f"Chien thang {threshold} tran",
            progress=min(wins, threshold),
            target=threshold,
            level=level,
            completed=wins >= threshold,
        )
        threshold *= 2
        level += 1

    db_service.upsert_user_achievement(
        user_id,
        code="online_100",
        title="Tham gia 100 van dau",
        progress=min(games, 100),
        target=100,
        level=1,
        completed=games >= 100,
    )

    rank_targets = ["Silver", "Platinum", "Diamond", "Master"]
    tier_order = ["Bronze", "Silver", "Platinum", "Diamond", "Master"]
    current_index = tier_order.index(tier) if tier in tier_order else 0
    for target in rank_targets:
        target_idx = tier_order.index(target)
        db_service.upsert_user_achievement(
            user_id,
            code=f"rank_{target.lower()}",
            title=f"Dat hang {target}",
            progress=1 if current_index >= target_idx else 0,
            target=1,
            level=target_idx,
            completed=current_index >= target_idx,
        )


def register(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()

    if len(username) < 3 or len(password) < 6:
        return {"error": "Username >= 3 va password >= 6 ky tu"}, 400

    if db_service.is_reserved_username(username):
        return {"error": "Username nay da duoc bao luu"}, 403

    user = auth_service.register_user(username, password)
    if not user:
        return {"error": "Username da ton tai"}, 409

    return {"user": user}, 201


def login(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()

    session = auth_service.login_user(username, password)
    if not session:
        return {"error": "Thong tin dang nhap khong dung"}, 401

    return session, 200


def me(token: str) -> Tuple[Dict[str, Any], int]:
    user = auth_service.get_user_from_token(token)
    if not user:
        return {"error": "Token khong hop le"}, 401

    db_service.normalize_user_rank(int(user["id"]))
    db_service.grant_weekly_rank_mail(int(user["id"]))
    refreshed = db_service.get_user_by_id(int(user["id"]))
    if refreshed:
        user = auth_service.sanitize_user(refreshed)

    return {"user": user}, 200


def leaderboard(limit: int, kind: str) -> Tuple[Dict[str, Any], int]:
    normalized = kind.strip().lower()
    if normalized not in {"ai", "room", "rank"}:
        normalized = "room"

    rows = db_service.get_leaderboard(limit, kind=normalized)
    return {"items": rows, "kind": normalized}, 200


def achievements(token: str) -> Tuple[Dict[str, Any], int]:
    user = auth_service.get_user_from_token(token)
    if not user:
        return {"error": "Token khong hop le"}, 401

    user_id = int(user["id"])
    wins = int(user.get("wins", 0))
    games = int(user.get("gamesPlayed", 0))
    tier = str(user.get("rankTier", "Bronze"))

    _sync_achievements_for_user(user_id, wins=wins, games=games, tier=tier)

    rows = db_service.list_user_achievements(user_id)
    return {
        "items": [
            {
                "id": item["code"],
                "title": item["title"],
                "progress": item["progress"],
                "target": item["target"],
                "completed": bool(item["completed"]),
                "level": item["level"],
                "updatedAt": item["updated_at"],
            }
            for item in rows
        ]
    }, 200


def update_profile(payload: Dict[str, Any], token: str) -> Tuple[Dict[str, Any], int]:
    user = auth_service.get_user_from_token(token)
    if not user:
        return {"error": "Token khong hop le"}, 401

    username_in_payload = payload.get("username", None)
    avatar_in_payload = payload.get("avatar", None)

    if username_in_payload is None and avatar_in_payload is None:
        return {"error": "Can it nhat mot truong de cap nhat"}, 400

    user_id = int(user["id"])

    if username_in_payload is not None:
        username = str(username_in_payload).strip()
        if len(username) < 3 or len(username) > 24:
            return {"error": "Username phai tu 3 den 24 ky tu"}, 400

        if db_service.is_reserved_username(username) and str(user.get("username", "")).upper() != "ADMIN":
            return {"error": "Username nay da duoc bao luu"}, 403

        update_state = db_service.update_username(user_id, username)
        if update_state == "exists":
            return {"error": "Username da ton tai"}, 409
        if update_state == "reserved":
            return {"error": "Username nay da duoc bao luu"}, 403
        if update_state == "not_found":
            return {"error": "Khong tim thay user"}, 404

    if avatar_in_payload is not None:
        avatar = str(avatar_in_payload).strip()
        if not avatar:
            return {"error": "Avatar khong hop le"}, 400
        db_service.update_user_avatar(user_id, avatar)

    updated = db_service.get_user_by_id(int(user["id"]))
    if not updated:
        return {"error": "Khong tim thay user"}, 404

    return {"user": auth_service.sanitize_user(updated)}, 200


def public_profile(user_id: int, rank_position: int | None = None) -> Tuple[Dict[str, Any], int]:
    db_service.normalize_user_rank(user_id)
    profile = db_service.get_public_user_profile(user_id)
    if not profile:
        return {"error": "Khong tim thay user"}, 404

    _sync_achievements_for_user(
        user_id,
        wins=int(profile.get("wins", 0)),
        games=int(profile.get("games_played", 0)),
        tier=str(profile.get("rank_tier", "Bronze")),
    )

    achievements_rows = db_service.list_user_achievements(user_id)
    normalized_tier, normalized_stars, normalized_streak = db_service.normalize_rank_state(
        str(profile.get("rank_tier", "Bronze")),
        int(profile.get("rank_stars", 0)),
        int(profile.get("rank_streak", 0)),
    )
    visual = db_service.rank_badge_info(
        normalized_tier,
        normalized_stars,
        rank_position=rank_position,
    )
    selected_title_code = str(profile.get("selected_title_code", ""))
    selected_title_name = db_service.get_selected_title_name(user_id, selected_title_code)

    return {
        "user": {
            "id": profile["id"],
            "username": profile["username"],
            "rating": profile["rating"],
            "wins": profile["wins"],
            "losses": profile["losses"],
            "draws": profile["draws"],
            "gamesPlayed": profile["games_played"],
            "winsVsAi": profile["wins_vs_ai"],
            "winsVsRoom": profile["wins_vs_room"],
            "winsRanked": profile.get("wins_ranked", 0),
            "rankPoints": profile["rank_points"],
            "rankTier": normalized_tier,
            "rankStars": normalized_stars,
            "rankStreak": normalized_streak,
            "avatar": profile.get("avatar", "🙂"),
            "gamesVsAi": profile.get("games_vs_ai", 0),
            "gamesVsRoom": profile.get("games_vs_room", 0),
            "gamesRanked": profile.get("games_ranked", 0),
            "selectedTitleCode": selected_title_code,
            "selectedTitleName": selected_title_name,
            "selectedFrameCode": profile.get("selected_frame_code", ""),
            "rankVisual": visual,
        },
        "achievements": [
            {
                "id": item["code"],
                "title": item["title"],
                "progress": item["progress"],
                "target": item["target"],
                "completed": bool(item["completed"]),
                "level": item["level"],
            }
            for item in achievements_rows
        ],
    }, 200


def mailbox(token: str) -> Tuple[Dict[str, Any], int]:
    user = auth_service.get_user_from_token(token)
    if not user:
        return {"error": "Token khong hop le"}, 401

    user_id = int(user["id"])
    db_service.grant_weekly_rank_mail(user_id)
    items = db_service.list_mailbox(user_id)
    return {"items": items}, 200


def claim_mail(mail_id: int, token: str) -> Tuple[Dict[str, Any], int]:
    user = auth_service.get_user_from_token(token)
    if not user:
        return {"error": "Token khong hop le"}, 401

    result = db_service.claim_mail_item(int(user["id"]), mail_id)
    if result is None:
        return {"error": "Khong tim thay thu"}, 404
    return result, 200


def claim_all_mail(token: str) -> Tuple[Dict[str, Any], int]:
    user = auth_service.get_user_from_token(token)
    if not user:
        return {"error": "Token khong hop le"}, 401

    result = db_service.claim_all_mail_items(int(user["id"]))
    return result, 200


def inventory(token: str) -> Tuple[Dict[str, Any], int]:
    user = auth_service.get_user_from_token(token)
    if not user:
        return {"error": "Token khong hop le"}, 401

    items = db_service.list_inventory(int(user["id"]))
    return {"items": items}, 200


def equip_item(payload: Dict[str, Any], token: str) -> Tuple[Dict[str, Any], int]:
    user = auth_service.get_user_from_token(token)
    if not user:
        return {"error": "Token khong hop le"}, 401

    item_code = str(payload.get("itemCode", "")).strip()
    if not item_code:
        return {"error": "itemCode khong hop le"}, 400

    ok = db_service.equip_inventory_item(int(user["id"]), item_code)
    if not ok:
        return {"error": "Khong tim thay vat pham"}, 404

    updated = db_service.get_user_by_id(int(user["id"]))
    if not updated:
        return {"user": user}, 200
    return {"user": auth_service.sanitize_user(updated)}, 200


def rank_catalog() -> Tuple[Dict[str, Any], int]:
    rows = []
    for key, info in db_service.RANK_META.items():
        rows.append(
            {
                "code": key.lower(),
                "display": info["display"],
                "title": info["title"],
                "frameDescription": info["frame"],
                "badgeImage": info["image"],
            }
        )
    return {"items": rows}, 200


def match_history(token: str, limit: int = 30) -> Tuple[Dict[str, Any], int]:
    user = auth_service.get_user_from_token(token)
    if not user:
        return {"error": "Token khong hop le"}, 401

    normalized_limit = max(1, min(100, int(limit)))
    items = db_service.list_user_match_history(int(user["id"]), limit=normalized_limit)
    return {"items": items}, 200


def match_replay(match_id: int, token: str) -> Tuple[Dict[str, Any], int]:
    user = auth_service.get_user_from_token(token)
    if not user:
        return {"error": "Token khong hop le"}, 401

    replay = db_service.get_match_replay(match_id, int(user["id"]))
    if not replay:
        return {"error": "Khong tim thay replay hoac khong co quyen"}, 404

    parsed = game_service.parse_match(replay["match"])
    return {
        "replay": {
            "matchId": parsed["id"],
            "mode": parsed["mode"],
            "matchType": parsed.get("match_type", "casual"),
            "boardSize": parsed["board_size"],
            "winLength": parsed["win_length"],
            "playersCount": parsed["players_count"],
            "players": parsed["players"],
            "status": parsed["status"],
            "winner": parsed["winner"],
            "participants": replay["participants"],
            "viewerPlayerIndex": replay["viewerPlayerIndex"],
            "moves": replay["moves"],
            "createdAt": replay["match"].get("created_at"),
            "updatedAt": replay["match"].get("updated_at"),
        }
    }, 200


def chat_filter_settings(token: str) -> Tuple[Dict[str, Any], int]:
    user = auth_service.get_user_from_token(token)
    if not user:
        return {"error": "Token khong hop le"}, 401

    words = db_service.get_custom_banned_words()
    return {"customBannedWords": words}, 200


def update_chat_filter_settings(payload: Dict[str, Any], token: str) -> Tuple[Dict[str, Any], int]:
    user = auth_service.get_user_from_token(token)
    if not user:
        return {"error": "Token khong hop le"}, 401

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
