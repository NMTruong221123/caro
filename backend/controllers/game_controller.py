from typing import Any, Dict, Tuple

from config.settings import (
    DEFAULT_BOARD_SIZE,
    DEFAULT_MULTI_PLAYERS,
    DEFAULT_WIN_LENGTH,
    MAX_BOARD_SIZE,
    MAX_MULTI_PLAYERS,
    MIN_MULTI_PLAYERS,
)

from backend.services import db_service, game_service
from backend.services.auth_service import get_user_from_token


VALID_MODES = {"ai", "multi"}


def _build_state_response(match: Dict[str, Any], moves: list[Dict[str, Any]]) -> Dict[str, Any]:
    parsed = game_service.parse_match(match)
    return {
        "matchId": parsed["id"],
        "mode": parsed["mode"],
        "matchType": parsed.get("match_type", "casual"),
        "aiLevel": parsed["ai_level"],
        "boardSize": parsed["board_size"],
        "winLength": parsed["win_length"],
        "playersCount": parsed["players_count"],
        "players": parsed["players"],
        "board": parsed["board"],
        "currentPlayer": parsed["current_player"],
        "status": parsed["status"],
        "winner": parsed["winner"],
        "moves": moves,
    }


def start_new_match(payload: Dict[str, Any], token: str = "") -> Tuple[Dict[str, Any], int]:
    mode = str(payload.get("mode", "ai")).lower()
    if mode not in VALID_MODES:
        return {"error": "Mode khong hop le"}, 400

    board_size = int(payload.get("boardSize", DEFAULT_BOARD_SIZE))
    win_length = int(payload.get("winLength", DEFAULT_WIN_LENGTH))
    players_count = int(payload.get("playersCount", DEFAULT_MULTI_PLAYERS))
    ai_level = str(payload.get("aiLevel", "medium")).lower()

    if board_size < 5 or board_size > MAX_BOARD_SIZE:
        return {"error": f"Kich thuoc ban co phai trong khoang 5-{MAX_BOARD_SIZE}"}, 400

    if win_length < 3 or win_length > board_size:
        return {"error": "Do dai chien thang khong hop le"}, 400

    if mode == "multi" and (players_count < MIN_MULTI_PLAYERS or players_count > MAX_MULTI_PLAYERS):
        return {"error": "So nguoi choi phai trong khoang 2-4"}, 400

    if mode == "ai":
        players_count = 2
        if ai_level not in {"easy", "medium", "hard"}:
            return {"error": "AI level phai la easy, medium hoac hard"}, 400
    else:
        ai_level = "medium"

    user = get_user_from_token(token) if token else None

    state = game_service.start_game_state(mode, board_size, players_count)

    match_id = db_service.create_match(
        mode=mode,
        board_size=board_size,
        win_length=win_length,
        players_count=state["players_count"],
        players=state["players"],
        board=state["board"],
        current_player=state["current_player"],
        ai_level=ai_level,
        match_type="casual",
        created_by_user_id=int(user["id"]) if user else None,
    )

    if user:
        db_service.create_match_participants(
            match_id,
            [
                {
                    "user_id": int(user["id"]),
                    "player_index": 1,
                    "room_id": None,
                }
            ],
        )

    match = db_service.get_match(match_id)
    assert match is not None
    return _build_state_response(match, []), 201


def get_match_state(match_id: int) -> Tuple[Dict[str, Any], int]:
    match = db_service.get_match(match_id)
    if not match:
        return {"error": "Khong tim thay tran"}, 404

    moves = db_service.list_moves(match_id)
    return _build_state_response(match, moves), 200


def play_move(payload: Dict[str, Any], token: str = "") -> Tuple[Dict[str, Any], int]:
    try:
        match_id = int(payload.get("matchId"))
        row = int(payload.get("row"))
        col = int(payload.get("col"))
    except (TypeError, ValueError):
        return {"error": "Du lieu nuoc di khong hop le"}, 400

    match = db_service.get_match(match_id)
    if not match:
        return {"error": "Khong tim thay tran"}, 404

    state = game_service.parse_match(match)
    if state["status"] != "playing":
        return {"error": "Tran da ket thuc"}, 400

    human_move = game_service.apply_player_move(state, row, col)
    if human_move is None:
        return {"error": "Nuoc di khong hop le"}, 400

    if state["mode"] == "ai":
        db_service.learn_ai_human_move(state["board_size"], row, col)

    turn = db_service.count_moves(match_id) + 1
    db_service.save_move(
        match_id=match_id,
        turn=turn,
        player=human_move["player"],
        row=human_move["row"],
        col=human_move["col"],
        shape=human_move["shape"],
        color=human_move["color"],
    )

    ai_heatmap = db_service.get_ai_heatmap(state["board_size"]) if state["mode"] == "ai" else None
    ai_move = game_service.maybe_make_ai_move(state, learned_heatmap=ai_heatmap)
    if ai_move is not None:
        turn = db_service.count_moves(match_id) + 1
        db_service.save_move(
            match_id=match_id,
            turn=turn,
            player=ai_move["player"],
            row=ai_move["row"],
            col=ai_move["col"],
            shape=ai_move["shape"],
            color=ai_move["color"],
        )

    db_service.update_match(
        match_id=match_id,
        board=state["board"],
        current_player=state["current_player"],
        status=state["status"],
        winner=state["winner"],
    )

    if state["mode"] == "ai" and state["status"] in {"finished", "draw"}:
        creator_id = match.get("created_by_user_id")
        requester = get_user_from_token(token) if token else None
        if creator_id and requester and int(requester["id"]) == int(creator_id):
            did_win = state["status"] == "finished" and int(state["winner"] or 0) == 1
            did_draw = state["status"] == "draw"
            db_service.record_ai_result(int(creator_id), won=did_win, draw=did_draw)

    updated_match = db_service.get_match(match_id)
    assert updated_match is not None
    moves = db_service.list_moves(match_id)
    return _build_state_response(updated_match, moves), 200
