import random
import re
import string
import time
import unicodedata
from collections import deque
from typing import Any, Dict, Optional

from config.settings import (
    CHAT_BANNED_WORDS,
    CHAT_SPAM_MAX_MESSAGES,
    CHAT_SPAM_WINDOW_SECONDS,
    MAX_BOARD_SIZE,
    RANK_QUEUE_MAX_DISTINCT_USERS_PER_IP,
    RANK_QUEUE_MAX_JOINS_PER_IP,
    RANK_QUEUE_MAX_JOINS_PER_USER,
    RANK_QUEUE_WINDOW_SECONDS,
)
from backend.services import db_service, game_service
from game.multiplayer import build_multiplayer_players, build_random_icon_players
from game.shapes import AI_TOKENS


_BANNED_WORDS = {str(item).lower() for item in CHAT_BANNED_WORDS}
_SPAM_WINDOW_SECONDS = CHAT_SPAM_WINDOW_SECONDS
_SPAM_MAX_MESSAGES = CHAT_SPAM_MAX_MESSAGES
_CHAT_RATE_TRACKER: dict[tuple[int, int], deque[float]] = {}
_CUSTOM_BANNED_CACHE: dict[str, Any] = {"words": set(), "loaded_at": 0.0}
_RANK_QUEUE: deque[int] = deque()
_RANK_QUEUE_META: dict[int, dict[str, Any]] = {}
_RANK_QUEUE_TIMEOUT_SECONDS = 120
_RANK_QUEUE_USER_RATE: dict[int, deque[float]] = {}
_RANK_QUEUE_IP_RATE: dict[str, deque[float]] = {}
_RANK_SECURITY_EVENTS: deque[dict[str, Any]] = deque(maxlen=200)

_RANK_TIER_ORDER = [name for name, _stars in db_service.RANK_TIERS]
_RANK_STAR_LIMIT = {name: stars for name, stars in db_service.RANK_TIERS}


def _room_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def create_room(owner_user_id: int, max_players: int, room_type: str = "casual") -> Dict[str, Any]:
    code = _room_code()
    while db_service.get_room_by_code(code):
        code = _room_code()

    room_id = db_service.create_room(code, owner_user_id, max_players, room_type=room_type)
    player_index = db_service.add_player_to_room(room_id, owner_user_id)
    assert player_index is not None

    room = db_service.get_room_by_code(code)
    assert room is not None
    return room_payload(room)


def join_room(code: str, user_id: int) -> Optional[Dict[str, Any]]:
    room = db_service.get_room_by_code(code)
    if not room:
        return None

    player_index = db_service.add_player_to_room(int(room["id"]), user_id)
    if player_index is None:
        return None

    updated = db_service.get_room_by_code(code)
    if not updated:
        return None
    return room_payload(updated)


def room_payload(room: Dict[str, Any]) -> Dict[str, Any]:
    players = db_service.list_room_players(int(room["id"]))
    return {
        "id": room["id"],
        "code": room["code"],
        "ownerUserId": room["owner_user_id"],
        "status": room["status"],
        "roomType": room.get("room_type", "casual"),
        "maxPlayers": room["max_players"],
        "matchId": room["match_id"],
        "players": players,
    }


def _next_active_player_index(current_player: int, active_indices: list[int]) -> Optional[int]:
    if not active_indices:
        return None

    ordered = sorted({int(item) for item in active_indices})
    current = int(current_player)
    if current in ordered:
        return current

    for index in ordered:
        if index > current:
            return index
    return ordered[0]


def get_room(code: str) -> Optional[Dict[str, Any]]:
    room = db_service.get_room_by_code(code)
    if not room:
        return None
    return room_payload(room)


def _assert_owner(room: Dict[str, Any], requester_user_id: int) -> None:
    if int(room["owner_user_id"]) != requester_user_id:
        raise PermissionError("Chi chu phong moi co quyen nay")


def _assert_owner_or_cohost(room: Dict[str, Any], requester_user_id: int) -> None:
    if int(room["owner_user_id"]) == requester_user_id:
        return

    room_id = int(room["id"])
    if db_service.is_room_cohost(room_id, requester_user_id):
        return

    raise PermissionError("Chi chu phong hoac co-host moi co quyen nay")


def _contains_banned_word(message: str) -> bool:
    banned_words = _effective_banned_words()

    folded = unicodedata.normalize("NFD", message.lower()).replace("đ", "d")
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    normalized = re.sub(r"[^a-z0-9]+", " ", folded).strip()
    compact = re.sub(r"\s+", "", normalized)

    tokens = normalized.split()
    if any(token in banned_words for token in tokens):
        return True

    for word in banned_words:
        pattern = r"\\b" + r"\\W*".join(re.escape(ch) for ch in word) + r"\\b"
        if re.search(pattern, folded):
            return True
        if word in compact:
            return True
    return False


def _effective_banned_words() -> set[str]:
    now = time.time()
    loaded_at = float(_CUSTOM_BANNED_CACHE.get("loaded_at", 0.0))
    if now - loaded_at > 10:
        custom_words = set(db_service.get_custom_banned_words())
        _CUSTOM_BANNED_CACHE["words"] = custom_words
        _CUSTOM_BANNED_CACHE["loaded_at"] = now

    custom = _CUSTOM_BANNED_CACHE.get("words", set())
    if not isinstance(custom, set):
        custom = set()
    return set(_BANNED_WORDS) | custom


def refresh_custom_banned_cache() -> None:
    _CUSTOM_BANNED_CACHE["loaded_at"] = 0.0


def _check_spam_limit(room_id: int, user_id: int) -> None:
    now = time.time()
    key = (room_id, user_id)
    bucket = _CHAT_RATE_TRACKER.setdefault(key, deque())

    while bucket and now - bucket[0] > _SPAM_WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= _SPAM_MAX_MESSAGES:
        raise ValueError("Ban gui tin nhan qua nhanh, vui long cho it giay")

    bucket.append(now)


def start_room_game(
    code: str,
    requester_user_id: int,
    board_size: int,
    win_length: int,
    match_type: str = "casual",
    enforce_owner: bool = True,
) -> Optional[Dict[str, Any]]:
    room = db_service.get_room_by_code(code)
    if not room:
        return None

    if enforce_owner:
        _assert_owner(room, requester_user_id)

    if str(room.get("status")) == "playing":
        raise ValueError("Phong dang co tran")

    if board_size < 5 or board_size > MAX_BOARD_SIZE:
        raise ValueError(f"Kich thuoc ban phai trong khoang 5-{MAX_BOARD_SIZE}")

    if win_length < 3 or win_length > board_size:
        raise ValueError("Do dai chien thang khong hop le")

    room_id = int(room["id"])
    room_players = db_service.list_room_players(room_id)
    player_count = len(room_players)

    if player_count < 2:
        raise ValueError("Can it nhat 2 nguoi trong phong de bat dau")

    room_type = str(room.get("room_type", "casual"))
    if room_type == "ranked":
        players = [
            {"shape": "x", "color": AI_TOKENS[0]["color"], "name": "Nguoi choi 1"},
            {"shape": "o", "color": AI_TOKENS[1]["color"], "name": "Nguoi choi 2"},
        ][:player_count]
    else:
        players = build_random_icon_players(player_count)
    board = game_service.start_game_state("multi", board_size, player_count)["board"]

    match_id = db_service.create_match(
        mode="online",
        board_size=board_size,
        win_length=win_length,
        players_count=player_count,
        players=players,
        board=board,
        current_player=1,
        ai_level="medium",
        match_type=match_type,
        created_by_user_id=requester_user_id,
    )

    db_service.create_match_participants(
        match_id,
        [
            {
                "user_id": int(player["user_id"]),
                "player_index": int(player["player_index"]),
                "room_id": room_id,
            }
            for player in room_players
        ],
    )

    db_service.set_room_match(room_id, match_id)

    match = db_service.get_match(match_id)
    if not match:
        return None

    state = game_service.parse_match(match)
    state["status"] = "playing"

    return {
        "room": room_payload(db_service.get_room_by_code(code) or room),
        "state": {
            "matchId": state["id"],
            "mode": state["mode"],
            "matchType": state.get("match_type", match_type),
            "boardSize": state["board_size"],
            "winLength": state["win_length"],
            "playersCount": state["players_count"],
            "players": state["players"],
            "board": state["board"],
            "currentPlayer": state["current_player"],
            "status": state["status"],
            "winner": state["winner"],
            "moves": [],
        },
    }


def process_online_move(code: str, user_id: int, row: int, col: int) -> Optional[Dict[str, Any]]:
    room = db_service.get_room_by_code(code)
    if not room or not room.get("match_id"):
        return None

    room_id = int(room["id"])
    match_id = int(room["match_id"])
    match = db_service.get_match(match_id)
    if not match:
        return None

    state = game_service.parse_match(match)
    if state["status"] != "playing":
        return None

    room_players = db_service.list_room_players(room_id)
    player_map = {int(player["player_index"]): int(player["user_id"]) for player in room_players}

    normalized_current = _next_active_player_index(int(state["current_player"]), list(player_map.keys()))
    if normalized_current is None:
        state["status"] = "draw"
        state["winner"] = None
        db_service.update_match(
            match_id=match_id,
            board=state["board"],
            current_player=int(state["current_player"]),
            status="draw",
            winner=None,
        )
        db_service.finish_room(room_id)
        updated_match = db_service.get_match(match_id)
        if not updated_match:
            return None
        parsed = game_service.parse_match(updated_match)
        moves = db_service.list_moves(match_id)
        return {
            "room": room_payload(db_service.get_room_by_code(code) or room),
            "state": {
                "matchId": parsed["id"],
                "mode": parsed["mode"],
                "matchType": parsed.get("match_type", "casual"),
                "boardSize": parsed["board_size"],
                "winLength": parsed["win_length"],
                "playersCount": parsed["players_count"],
                "players": parsed["players"],
                "board": parsed["board"],
                "currentPlayer": parsed["current_player"],
                "status": parsed["status"],
                "winner": parsed["winner"],
                "moves": moves,
                "roomPlayers": room_players,
            },
        }

    if normalized_current != int(state["current_player"]):
        state["current_player"] = normalized_current

    expected_user_id = player_map.get(int(state["current_player"]))
    if expected_user_id != user_id:
        return None

    move = game_service.apply_player_move(state, row, col)
    if move is None:
        return None

    if state["status"] == "playing":
        next_player = _next_active_player_index(int(state["current_player"]), list(player_map.keys()))
        if next_player is None:
            state["status"] = "draw"
            state["winner"] = None
        else:
            state["current_player"] = next_player

    turn = db_service.count_moves(match_id) + 1
    db_service.save_move(
        match_id=match_id,
        turn=turn,
        player=move["player"],
        row=move["row"],
        col=move["col"],
        shape=move["shape"],
        color=move["color"],
    )

    db_service.update_match(
        match_id=match_id,
        board=state["board"],
        current_player=state["current_player"],
        status=state["status"],
        winner=state["winner"],
    )

    if state["status"] in {"finished", "draw"}:
        db_service.finish_room(room_id)
        is_draw = state["status"] == "draw"
        winner_index = None if is_draw else int(state["winner"])
        db_service.apply_elo_results(
            room_players,
            winner_index=winner_index,
            is_draw=is_draw,
            ranked=str(match.get("match_type", "casual")) == "ranked",
        )

    updated_match = db_service.get_match(match_id)
    if not updated_match:
        return None

    parsed = game_service.parse_match(updated_match)
    moves = db_service.list_moves(match_id)

    return {
        "room": room_payload(db_service.get_room_by_code(code) or room),
        "state": {
            "matchId": parsed["id"],
            "mode": parsed["mode"],
            "matchType": parsed.get("match_type", "casual"),
            "boardSize": parsed["board_size"],
            "winLength": parsed["win_length"],
            "playersCount": parsed["players_count"],
            "players": parsed["players"],
            "board": parsed["board"],
            "currentPlayer": parsed["current_player"],
            "status": parsed["status"],
            "winner": parsed["winner"],
            "moves": moves,
            "roomPlayers": room_players,
        },
    }


def get_room_match_state(code: str) -> Optional[Dict[str, Any]]:
    room = db_service.get_room_by_code(code)
    if not room or not room.get("match_id"):
        return None

    match_id = int(room["match_id"])
    match = db_service.get_match(match_id)
    if not match:
        return None

    room_players = db_service.list_room_players(int(room["id"]))
    parsed = game_service.parse_match(match)
    moves = db_service.list_moves(match_id)
    return {
        "matchId": parsed["id"],
        "mode": parsed["mode"],
        "matchType": parsed.get("match_type", "casual"),
        "boardSize": parsed["board_size"],
        "winLength": parsed["win_length"],
        "playersCount": parsed["players_count"],
        "players": parsed["players"],
        "board": parsed["board"],
        "currentPlayer": parsed["current_player"],
        "status": parsed["status"],
        "winner": parsed["winner"],
        "moves": moves,
        "roomPlayers": room_players,
    }


def get_active_room_session(user_id: int) -> Optional[Dict[str, Any]]:
    room = db_service.get_active_room_for_user(user_id)
    if not room:
        return None

    code = str(room.get("code", ""))
    if not code:
        return None

    payload = room_payload(room)
    state = get_room_match_state(code)
    return {
        "room": payload,
        "state": state,
    }


def add_chat_message(code: str, user_id: int, message: str) -> Optional[Dict[str, Any]]:
    room = db_service.get_room_by_code(code)
    if not room:
        return None

    clean_message = message.strip()
    if not clean_message:
        return None

    if len(clean_message) > 300:
        clean_message = clean_message[:300]

    room_id = int(room["id"])
    members = db_service.list_room_players(room_id)
    member_user_ids = {int(item["user_id"]) for item in members}
    if user_id not in member_user_ids:
        return None

    if db_service.is_user_muted_in_room(room_id, user_id):
        raise PermissionError("Ban dang bi mute trong phong")

    if _contains_banned_word(clean_message):
        raise ValueError("Tin nhan chua tu ngu khong phu hop")

    _check_spam_limit(room_id, user_id)

    saved = db_service.save_room_message(room_id, user_id, clean_message)
    return {
        "id": saved["id"],
        "roomCode": code,
        "userId": saved["user_id"],
        "username": saved["username"],
        "message": saved["message"],
        "createdAt": saved["created_at"],
    }


def get_chat_history(code: str, user_id: int, limit: int = 50) -> Optional[list[Dict[str, Any]]]:
    room = db_service.get_room_by_code(code)
    if not room:
        return None

    room_id = int(room["id"])
    members = db_service.list_room_players(room_id)
    member_user_ids = {int(item["user_id"]) for item in members}
    if user_id not in member_user_ids:
        return None

    rows = db_service.list_room_messages(room_id, limit=limit)
    return [
        {
            "id": item["id"],
            "roomCode": code,
            "userId": item["user_id"],
            "username": item["username"],
            "message": item["message"],
            "createdAt": item["created_at"],
        }
        for item in rows
    ]


def owner_set_mute(code: str, owner_user_id: int, target_user_id: int, muted: bool) -> Optional[Dict[str, Any]]:
    room = db_service.get_room_by_code(code)
    if not room:
        return None

    _assert_owner_or_cohost(room, owner_user_id)
    room_id = int(room["id"])

    if owner_user_id == target_user_id:
        raise ValueError("Khong the tu mute chinh minh")

    members = db_service.list_room_players(room_id)
    member_user_ids = {int(item["user_id"]) for item in members}
    if target_user_id not in member_user_ids:
        raise ValueError("Nguoi choi khong ton tai trong phong")

    db_service.set_room_mute(room_id, target_user_id, owner_user_id, muted)
    updated = db_service.get_room_by_code(code)
    if not updated:
        return None
    return room_payload(updated)


def owner_kick_member(code: str, owner_user_id: int, target_user_id: int) -> Optional[Dict[str, Any]]:
    room = db_service.get_room_by_code(code)
    if not room:
        return None

    _assert_owner_or_cohost(room, owner_user_id)
    room_id = int(room["id"])

    if owner_user_id == target_user_id:
        raise ValueError("Khong the tu kick chinh minh")

    if target_user_id == int(room["owner_user_id"]):
        raise ValueError("Khong the kick chu phong")

    room_players = db_service.list_room_players(room_id)
    target_player = next((item for item in room_players if int(item["user_id"]) == target_user_id), None)
    if not target_player:
        raise ValueError("Nguoi choi khong ton tai trong phong")

    room_status = str(room.get("status"))
    system_message: Optional[str] = None

    if room_status == "playing" and room.get("match_id"):
        match_id = int(room["match_id"])
        match = db_service.get_match(match_id)
        if match:
            match_state = game_service.parse_match(match)
            if match_state["status"] == "playing":
                target_index = int(target_player["player_index"])
                ranked = str(match.get("match_type", "casual")) == "ranked"

                # 2-nguoi: kick trong tran duoc tinh la thua ky thuat va ket thuc tran.
                if len(room_players) <= 2:
                    survivor_indices = [
                        int(player["player_index"])
                        for player in room_players
                        if int(player["player_index"]) != target_index
                    ]
                    winner_index = survivor_indices[0] if survivor_indices else None
                    status = "finished" if winner_index is not None else "draw"
                    db_service.update_match(
                        match_id=match_id,
                        board=match_state["board"],
                        current_player=match_state["current_player"],
                        status=status,
                        winner=winner_index,
                    )
                    db_service.finish_room(room_id)
                    db_service.apply_elo_results(
                        room_players,
                        winner_index=winner_index,
                        is_draw=winner_index is None,
                        ranked=ranked,
                    )

                    deleted = db_service.remove_player_from_room(room_id, target_user_id)
                    if not deleted:
                        raise ValueError("Nguoi choi khong ton tai trong phong")

                    updated = db_service.get_room_by_code(code)
                    if not updated:
                        return None
                    system_message = f"Nguoi choi {target_player['username']} bi xu thua ky thuat va bi kick khoi phong."
                    return {
                        "room": room_payload(updated),
                        "systemMessage": system_message,
                    }

                # >2 nguoi: nguoi bi kick bi thua ky thuat, tran tiep tuc cho cac nguoi con lai.
                deleted = db_service.remove_player_from_room(room_id, target_user_id)
                if not deleted:
                    raise ValueError("Nguoi choi khong ton tai trong phong")

                remaining_players = db_service.list_room_players(room_id)
                kicked_opponents = [
                    player for player in room_players if int(player["user_id"]) != int(target_user_id)
                ]
                db_service.apply_forfeit_loss(target_player, kicked_opponents, ranked=ranked)

                if not remaining_players:
                    db_service.update_match(
                        match_id=match_id,
                        board=match_state["board"],
                        current_player=match_state["current_player"],
                        status="draw",
                        winner=None,
                    )
                    db_service.finish_room(room_id)
                elif len(remaining_players) == 1:
                    winner_index = int(remaining_players[0]["player_index"])
                    db_service.update_match(
                        match_id=match_id,
                        board=match_state["board"],
                        current_player=winner_index,
                        status="finished",
                        winner=winner_index,
                    )
                    db_service.finish_room(room_id)
                else:
                    remaining_indices = sorted(int(item["player_index"]) for item in remaining_players)
                    current_idx = int(match_state["current_player"])

                    next_player = current_idx
                    if current_idx not in remaining_indices:
                        next_player = remaining_indices[0]
                        for idx in remaining_indices:
                            if idx > current_idx:
                                next_player = idx
                                break

                    db_service.update_match(
                        match_id=match_id,
                        board=match_state["board"],
                        current_player=next_player,
                        status="playing",
                        winner=None,
                    )

                updated = db_service.get_room_by_code(code)
                if not updated:
                    return None
                system_message = f"Nguoi choi {target_player['username']} bi xu thua ky thuat va bi kick khoi phong."
                return {
                    "room": room_payload(updated),
                    "systemMessage": system_message,
                }

    deleted = db_service.remove_player_from_room(room_id, target_user_id)
    if not deleted:
        raise ValueError("Nguoi choi khong ton tai trong phong")

    updated = db_service.get_room_by_code(code)
    if not updated:
        return None
    system_message = f"Nguoi choi {target_player['username']} da bi kick khoi phong."
    return {
        "room": room_payload(updated),
        "systemMessage": system_message,
    }


def owner_set_cohost(code: str, owner_user_id: int, target_user_id: int, enabled: bool) -> Optional[Dict[str, Any]]:
    room = db_service.get_room_by_code(code)
    if not room:
        return None

    _assert_owner(room, owner_user_id)
    room_id = int(room["id"])

    if target_user_id in {owner_user_id, int(room["owner_user_id"])}:
        raise ValueError("Chu phong luon la quan tri vien chinh")

    members = db_service.list_room_players(room_id)
    member_user_ids = {int(item["user_id"]) for item in members}
    if target_user_id not in member_user_ids:
        raise ValueError("Nguoi choi khong ton tai trong phong")

    db_service.set_room_cohost(room_id, target_user_id, owner_user_id, enabled)
    updated = db_service.get_room_by_code(code)
    if not updated:
        return None
    return room_payload(updated)


def owner_transfer_ownership(code: str, owner_user_id: int, target_user_id: int) -> Optional[Dict[str, Any]]:
    room = db_service.get_room_by_code(code)
    if not room:
        return None

    _assert_owner(room, owner_user_id)
    room_id = int(room["id"])

    if target_user_id == owner_user_id:
        raise ValueError("Ban da la chu phong")

    members = db_service.list_room_players(room_id)
    target = next((item for item in members if int(item["user_id"]) == target_user_id), None)
    if not target:
        raise ValueError("Nguoi choi khong ton tai trong phong")

    if not db_service.is_room_cohost(room_id, target_user_id):
        raise ValueError("Chi co-host moi co the duoc chuyen quyen chu phong")

    db_service.transfer_room_owner(room_id, old_owner_user_id=owner_user_id, new_owner_user_id=target_user_id)

    updated = db_service.get_room_by_code(code)
    if not updated:
        return None

    return {
        "room": room_payload(updated),
        "systemMessage": f"Chu phong da duoc chuyen cho {target['username']}.",
    }


def handle_user_disconnect(user_id: int) -> Optional[Dict[str, Any]]:
    room = db_service.get_active_room_for_user(user_id)
    if not room:
        return None

    room_id = int(room["id"])
    code = str(room.get("code", ""))
    if not code:
        return None

    room_players = db_service.list_room_players(room_id)
    leaving_player = next((item for item in room_players if int(item["user_id"]) == int(user_id)), None)
    if not leaving_player:
        return None

    match_id = int(room.get("match_id") or 0)
    if match_id <= 0:
        return None

    match = db_service.get_match(match_id)
    if not match:
        return None

    match_state = game_service.parse_match(match)
    if str(match_state.get("status")) != "playing":
        return None

    ranked = str(match.get("match_type", room.get("room_type", "casual"))) == "ranked"

    # 1v1 ranked/casual: disconnect counts as technical loss.
    if len(room_players) <= 2:
        survivor_indices = [
            int(player["player_index"])
            for player in room_players
            if int(player["user_id"]) != int(user_id)
        ]
        winner_index = survivor_indices[0] if survivor_indices else None
        status = "finished" if winner_index is not None else "draw"
        current_player = winner_index if winner_index is not None else int(match_state["current_player"])

        db_service.update_match(
            match_id=match_id,
            board=match_state["board"],
            current_player=current_player,
            status=status,
            winner=winner_index,
        )
        db_service.finish_room(room_id)
        db_service.apply_elo_results(
            room_players,
            winner_index=winner_index,
            is_draw=winner_index is None,
            ranked=ranked,
        )
        db_service.remove_player_from_room(room_id, int(user_id))

        updated_room = db_service.get_room_by_code(code) or room
        return {
            "code": code,
            "room": room_payload(updated_room),
            "state": get_room_match_state(code),
            "systemMessage": f"Nguoi choi {leaving_player['username']} da roi tran va bi xu thua ky thuat.",
        }

    # >2 players: remove disconnected player, keep board state and continue with active players.
    db_service.remove_player_from_room(room_id, int(user_id))
    opponents = [item for item in room_players if int(item["user_id"]) != int(user_id)]
    db_service.apply_forfeit_loss(leaving_player, opponents, ranked=ranked)

    remaining_players = db_service.list_room_players(room_id)
    if not remaining_players:
        db_service.update_match(
            match_id=match_id,
            board=match_state["board"],
            current_player=int(match_state["current_player"]),
            status="draw",
            winner=None,
        )
        db_service.finish_room(room_id)
    elif len(remaining_players) == 1:
        winner_index = int(remaining_players[0]["player_index"])
        db_service.update_match(
            match_id=match_id,
            board=match_state["board"],
            current_player=winner_index,
            status="finished",
            winner=winner_index,
        )
        db_service.finish_room(room_id)
    else:
        next_player = _next_active_player_index(
            int(match_state["current_player"]),
            [int(item["player_index"]) for item in remaining_players],
        )
        db_service.update_match(
            match_id=match_id,
            board=match_state["board"],
            current_player=next_player or int(match_state["current_player"]),
            status="playing",
            winner=None,
        )

    updated_room = db_service.get_room_by_code(code) or room
    return {
        "code": code,
        "room": room_payload(updated_room),
        "state": get_room_match_state(code),
        "systemMessage": f"Nguoi choi {leaving_player['username']} da roi tran, luot cua nguoi nay se bi khoa.",
    }


def _cleanup_rank_queue(now: Optional[float] = None) -> list[int]:
    current = now if now is not None else time.time()
    timed_out: list[int] = []
    alive: deque[int] = deque()
    for uid in _RANK_QUEUE:
        meta = _RANK_QUEUE_META.get(uid)
        if not meta:
            continue
        joined_at = float(meta.get("joined_at", current))
        if current - joined_at > _RANK_QUEUE_TIMEOUT_SECONDS:
            timed_out.append(uid)
            _RANK_QUEUE_META.pop(uid, None)
        else:
            alive.append(uid)

    _RANK_QUEUE.clear()
    _RANK_QUEUE.extend(alive)
    return timed_out


def _rank_index(tier: str) -> int:
    return _RANK_TIER_ORDER.index(tier) if tier in _RANK_TIER_ORDER else 0


def _can_match_by_stars(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_tier, left_stars, _left_streak = db_service.normalize_rank_state(
        str(left.get("rank_tier", "Bronze")),
        int(left.get("rank_stars", 0)),
        0,
    )
    right_tier, right_stars, _right_streak = db_service.normalize_rank_state(
        str(right.get("rank_tier", "Bronze")),
        int(right.get("rank_stars", 0)),
        0,
    )

    left_idx = _rank_index(left_tier)
    right_idx = _rank_index(right_tier)

    if left_idx == right_idx:
        return abs(left_stars - right_stars) <= 2

    if abs(left_idx - right_idx) != 1:
        return False

    lower = left if left_idx < right_idx else right
    upper = right if left_idx < right_idx else left
    lower_tier = left_tier if left_idx < right_idx else right_tier
    lower_stars = left_stars if left_idx < right_idx else right_stars
    upper_stars = right_stars if left_idx < right_idx else left_stars
    lower_max = max(1, int(_RANK_STAR_LIMIT.get(lower_tier, 3)) - 1)

    # Adjacent tiers only match if both users are close to the tier boundary.
    return lower_stars >= lower_max and upper_stars <= 1


def _match_distance(left: dict[str, Any], right: dict[str, Any]) -> int:
    left_tier, left_stars, _left_streak = db_service.normalize_rank_state(
        str(left.get("rank_tier", "Bronze")),
        int(left.get("rank_stars", 0)),
        0,
    )
    right_tier, right_stars, _right_streak = db_service.normalize_rank_state(
        str(right.get("rank_tier", "Bronze")),
        int(right.get("rank_stars", 0)),
        0,
    )
    left_idx = _rank_index(left_tier)
    right_idx = _rank_index(right_tier)
    return abs((left_idx * 10 + left_stars) - (right_idx * 10 + right_stars))


def _security_event(kind: str, user_id: int, sid: str, message: str, ip_address: str = "") -> None:
    _RANK_SECURITY_EVENTS.appendleft(
        {
            "kind": kind,
            "userId": user_id,
            "sid": sid,
            "ipAddress": ip_address,
            "message": message,
            "createdAt": time.time(),
        }
    )


def list_recent_rank_security_events(limit: int = 50) -> list[dict[str, Any]]:
    return list(_RANK_SECURITY_EVENTS)[: max(1, limit)]


def get_rank_queue_stats() -> Dict[str, Any]:
    per_ip: Dict[str, int] = {}
    for meta in _RANK_QUEUE_META.values():
        ip_address = str(meta.get("ip_address", "")).strip()
        if not ip_address:
            continue
        per_ip[ip_address] = per_ip.get(ip_address, 0) + 1

    return {
        "queueSize": len(_RANK_QUEUE),
        "queuedUsers": list(_RANK_QUEUE),
        "queuedPerIp": per_ip,
    }


def _trim_rate_bucket(bucket: deque[float], now: float) -> None:
    while bucket and now - bucket[0] > RANK_QUEUE_WINDOW_SECONDS:
        bucket.popleft()


def _count_queued_users_for_ip(ip_address: str) -> int:
    if not ip_address:
        return 0
    return sum(
        1
        for meta in _RANK_QUEUE_META.values()
        if str(meta.get("ip_address", "")) == ip_address
    )


def _check_rank_queue_security(user_id: int, sid: str, ip_address: str = "") -> Optional[str]:
    now = time.time()

    user_bucket = _RANK_QUEUE_USER_RATE.setdefault(user_id, deque())
    _trim_rate_bucket(user_bucket, now)
    if len(user_bucket) >= RANK_QUEUE_MAX_JOINS_PER_USER:
        _security_event("user_rate_limit", user_id, sid, "Join rank queue qua nhanh", ip_address)
        return "rate_limited"

    if ip_address:
        ip_bucket = _RANK_QUEUE_IP_RATE.setdefault(ip_address, deque())
        _trim_rate_bucket(ip_bucket, now)
        if len(ip_bucket) >= RANK_QUEUE_MAX_JOINS_PER_IP:
            _security_event("ip_rate_limit", user_id, sid, "IP join queue qua nhanh", ip_address)
            return "ip_rate_limited"

        queued_same_ip = _count_queued_users_for_ip(ip_address)
        if queued_same_ip >= RANK_QUEUE_MAX_DISTINCT_USERS_PER_IP:
            _security_event("ip_multi_account", user_id, sid, "Nhieu tai khoan dang queue cung IP", ip_address)
            return "multi_account_suspected"

    user_bucket.append(now)
    if ip_address:
        _RANK_QUEUE_IP_RATE.setdefault(ip_address, deque()).append(now)

    return None


def rank_queue_cancel(user_id: int, sid: Optional[str] = None) -> Dict[str, Any]:
    meta = _RANK_QUEUE_META.get(user_id)
    if not meta:
        return {"removed": False, "queueSize": len(_RANK_QUEUE)}

    if sid and str(meta.get("sid")) != sid:
        return {"removed": False, "queueSize": len(_RANK_QUEUE), "reason": "tab_mismatch"}

    _RANK_QUEUE_META.pop(user_id, None)
    remaining = [uid for uid in _RANK_QUEUE if uid != user_id]
    _RANK_QUEUE.clear()
    _RANK_QUEUE.extend(remaining)
    return {"removed": True, "queueSize": len(_RANK_QUEUE)}


def rank_queue_join(user_id: int, sid: str, ip_address: str = "", user_agent: str = "") -> Dict[str, Any]:
    timed_out_users = _cleanup_rank_queue()

    existing = _RANK_QUEUE_META.get(user_id)
    if existing:
        if str(existing.get("sid")) != sid:
            return {
                "matched": False,
                "queueSize": len(_RANK_QUEUE),
                "reason": "already_searching_another_tab",
                "timedOutUsers": timed_out_users,
            }
        existing["joined_at"] = time.time()
        return {
            "matched": False,
            "queueSize": len(_RANK_QUEUE),
            "reason": "already_in_queue",
            "timedOutUsers": timed_out_users,
        }

    security_reason = _check_rank_queue_security(user_id, sid, ip_address=ip_address)
    if security_reason:
        return {
            "matched": False,
            "queueSize": len(_RANK_QUEUE),
            "reason": security_reason,
            "timedOutUsers": timed_out_users,
        }

    db_service.normalize_user_rank(user_id)
    user = db_service.get_user_by_id(user_id)
    rank_tier, rank_stars, _rank_streak = db_service.normalize_rank_state(
        str((user or {}).get("rank_tier", "Bronze")),
        int((user or {}).get("rank_stars", 0)),
        int((user or {}).get("rank_streak", 0)),
    )

    _RANK_QUEUE_META[user_id] = {
        "sid": sid,
        "joined_at": time.time(),
        "rank_tier": rank_tier,
        "rank_stars": rank_stars,
        "ip_address": ip_address,
        "user_agent": user_agent,
    }
    _RANK_QUEUE.append(user_id)

    if len(_RANK_QUEUE) < 2:
        return {"matched": False, "queueSize": len(_RANK_QUEUE), "timedOutUsers": timed_out_users}

    user_a = None
    user_b = None
    best_score = None
    queue_list = list(_RANK_QUEUE)
    for i, left in enumerate(queue_list):
        left_meta = _RANK_QUEUE_META.get(left, {})
        for right in queue_list[i + 1 :]:
            right_meta = _RANK_QUEUE_META.get(right, {})
            if not _can_match_by_stars(left_meta, right_meta):
                continue

            score = _match_distance(left_meta, right_meta)
            if best_score is None or score < best_score:
                best_score = score
                user_a, user_b = left, right

    if user_a is None or user_b is None:
        return {"matched": False, "queueSize": len(_RANK_QUEUE), "timedOutUsers": timed_out_users}

    remaining = [uid for uid in _RANK_QUEUE if uid not in {user_a, user_b}]
    _RANK_QUEUE.clear()
    _RANK_QUEUE.extend(remaining)

    _RANK_QUEUE_META.pop(user_a, None)
    _RANK_QUEUE_META.pop(user_b, None)

    room = create_room(owner_user_id=user_a, max_players=2, room_type="ranked")
    join_room(room["code"], user_b)
    started = start_room_game(
        code=room["code"],
        requester_user_id=user_a,
        board_size=15,
        win_length=5,
        match_type="ranked",
        enforce_owner=False,
    )
    if not started:
        return {"matched": False, "queueSize": len(_RANK_QUEUE), "timedOutUsers": timed_out_users}

    return {
        "matched": True,
        "players": [user_a, user_b],
        "room": started["room"],
        "state": started["state"],
        "timedOutUsers": timed_out_users,
    }
