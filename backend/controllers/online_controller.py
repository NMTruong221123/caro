from typing import Any, Dict, Tuple

from backend.services import auth_service, online_service


def _validate_token(token: str):
    return auth_service.get_user_from_token(token)


def create_room(payload: Dict[str, Any], token: str) -> Tuple[Dict[str, Any], int]:
    user = _validate_token(token)
    if not user:
        return {"error": "Unauthorized"}, 401

    max_players = int(payload.get("maxPlayers", 4))
    if max_players < 2 or max_players > 4:
        return {"error": "maxPlayers phai trong khoang 2-4"}, 400

    room = online_service.create_room(int(user["id"]), max_players)
    return {"room": room}, 201


def join_room(payload: Dict[str, Any], token: str) -> Tuple[Dict[str, Any], int]:
    user = _validate_token(token)
    if not user:
        return {"error": "Unauthorized"}, 401

    code = str(payload.get("code", "")).strip().upper()
    if not code:
        return {"error": "Thieu ma phong"}, 400

    room = online_service.join_room(code, int(user["id"]))
    if not room:
        return {"error": "Khong vao duoc phong"}, 400

    return {"room": room}, 200


def room_detail(code: str, token: str) -> Tuple[Dict[str, Any], int]:
    user = _validate_token(token)
    if not user:
        return {"error": "Unauthorized"}, 401

    room = online_service.get_room(code.upper())
    if not room:
        return {"error": "Khong tim thay phong"}, 404

    return {"room": room}, 200


def active_room_session(token: str) -> Tuple[Dict[str, Any], int]:
    user = _validate_token(token)
    if not user:
        return {"error": "Unauthorized"}, 401

    payload = online_service.get_active_room_session(int(user["id"]))
    return {"session": payload}, 200
