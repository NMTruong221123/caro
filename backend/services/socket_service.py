from datetime import datetime, timezone
import importlib.util
import os

from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room

from backend.services import auth_service, online_service


def _async_backend_available(mode: str) -> bool:
    normalized = str(mode or "").strip().lower()
    if normalized == "threading":
        return True
    if normalized == "eventlet":
        return importlib.util.find_spec("eventlet") is not None
    if normalized in {"gevent", "gevent_uwsgi"}:
        return importlib.util.find_spec("gevent") is not None
    return False


def _resolve_async_mode() -> str:
    requested = str(os.getenv("SOCKETIO_ASYNC_MODE", "")).strip().lower()
    valid_modes = {"threading", "eventlet", "gevent", "gevent_uwsgi"}

    if requested in valid_modes and _async_backend_available(requested):
        return requested

    for candidate in ("eventlet", "gevent", "threading"):
        if _async_backend_available(candidate):
            return candidate

    return "threading"

socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode=_resolve_async_mode(),
)
CONNECTED_USERS: dict[str, dict[str, object]] = {}
USER_SOCKETS: dict[int, set[str]] = {}


def get_connected_stats() -> dict[str, int]:
    return {
        "onlineUsers": len(USER_SOCKETS),
        "openSockets": len(CONNECTED_USERS),
    }


def _emit_system_chat(code: str, message: str) -> None:
    emit(
        "room_chat_message",
        {
            "id": f"system-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
            "roomCode": code,
            "userId": 0,
            "username": "He thong",
            "message": message,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "system": True,
        },
        to=code,
    )


@socketio.on("connect")
def on_connect(auth):
    token = ""
    if isinstance(auth, dict):
        token = str(auth.get("token", ""))
    user = auth_service.get_user_from_token(token)
    if not user:
        return False

    CONNECTED_USERS[request.sid] = {
        "user_id": int(user["id"]),
        "username": str(user["username"]),
        "ip_address": str(request.headers.get("X-Forwarded-For", request.remote_addr or "")),
        "user_agent": str(request.headers.get("User-Agent", "")),
    }
    USER_SOCKETS.setdefault(int(user["id"]), set()).add(request.sid)
    emit("connected", {"ok": True, "user": user})


@socketio.on("disconnect")
def on_disconnect():
    context = CONNECTED_USERS.pop(request.sid, None)
    if not context:
        return
    uid = int(context.get("user_id", 0))
    sockets = USER_SOCKETS.get(uid)
    if not sockets:
        return
    sockets.discard(request.sid)
    if not sockets:
        USER_SOCKETS.pop(uid, None)
        online_service.rank_queue_cancel(uid, sid=request.sid)

        disconnect_result = online_service.handle_user_disconnect(uid)
        if disconnect_result:
            code = str(disconnect_result.get("code", ""))
            if code:
                payload = {"room": disconnect_result.get("room")}
                state = disconnect_result.get("state")
                if state:
                    payload["state"] = state

                emit("room_state", payload, to=code)
                system_message = disconnect_result.get("systemMessage")
                if system_message:
                    _emit_system_chat(code, str(system_message))


@socketio.on("rank_queue_join")
def on_rank_queue_join():
    context = CONNECTED_USERS.get(request.sid)
    user_id = int(context["user_id"]) if context else 0
    if user_id <= 0:
        emit("room_error", {"error": "Ban can dang nhap de vao queue rank"})
        return

    ip_address = str(context.get("ip_address", "")) if context else ""
    user_agent = str(context.get("user_agent", "")) if context else ""
    result = online_service.rank_queue_join(user_id, request.sid, ip_address=ip_address, user_agent=user_agent)
    for timed_out_uid in result.get("timedOutUsers", []):
        for sid in USER_SOCKETS.get(int(timed_out_uid), set()):
            emit("rank_queue_timeout", {"message": "Tim tran rank da het thoi gian, vui long tim lai."}, to=sid)

    reason = str(result.get("reason", ""))
    if reason == "already_searching_another_tab":
        emit("room_error", {"error": "Tai khoan dang tim tran o tab khac"}, to=request.sid)
        return
    if reason == "already_in_queue":
        emit("rank_queue_waiting", {"queueSize": int(result.get("queueSize", 1))}, to=request.sid)
        return
    if reason in {"rate_limited", "ip_rate_limited", "multi_account_suspected"}:
        emit("room_error", {"error": "Hang rank tam khoa tam thoi do hoat dong bat thuong. Vui long thu lai sau."}, to=request.sid)
        return

    if not result.get("matched"):
        emit("rank_queue_waiting", {"queueSize": int(result.get("queueSize", 1))}, to=request.sid)
        return

    room_code = str(result["room"]["code"])
    player_ids = [int(item) for item in result.get("players", [])]
    for pid in player_ids:
        for sid in USER_SOCKETS.get(pid, set()):
            join_room(room_code, sid=sid)
            emit("rank_queue_matched", {"code": room_code}, to=sid)

    emit("room_state", {"room": result["room"], "state": result["state"]}, to=room_code)


@socketio.on("rank_queue_cancel")
def on_rank_queue_cancel():
    context = CONNECTED_USERS.get(request.sid)
    user_id = int(context["user_id"]) if context else 0
    if user_id <= 0:
        return

    result = online_service.rank_queue_cancel(user_id, sid=request.sid)
    if result.get("removed"):
        emit("rank_queue_canceled", {"queueSize": int(result.get("queueSize", 0))}, to=request.sid)


@socketio.on("join_room")
def on_join_room(payload):
    code = str((payload or {}).get("code", "")).upper().strip()
    if not code:
        emit("room_error", {"error": "Thieu ma phong"})
        return

    join_room(code)
    context = CONNECTED_USERS.get(request.sid)
    user_id = int(context["user_id"]) if context else 0
    room = online_service.join_room(code, user_id)
    if not room:
        emit("room_error", {"error": "Khong vao duoc phong"})
        return

    emit("room_state", {"room": room}, to=code)
    chat_history = online_service.get_chat_history(code, user_id, limit=50)
    if chat_history is not None:
        emit("room_chat_history", {"code": code, "messages": chat_history})


@socketio.on("start_room_game")
def on_start_room_game(payload):
    data = payload or {}
    code = str(data.get("code", "")).upper().strip()
    try:
        board_size = int(data.get("boardSize", 15))
        win_length = int(data.get("winLength", 5))
    except (TypeError, ValueError):
        emit("room_error", {"error": "Thong so bat dau tran khong hop le"})
        return
    context = CONNECTED_USERS.get(request.sid)
    user_id = int(context["user_id"]) if context else 0

    try:
        created = online_service.start_room_game(code, user_id, board_size, win_length)
        if not created:
            emit("room_error", {"error": "Khong the bat dau tran"})
            return
    except PermissionError as exc:
        emit("room_error", {"error": str(exc)})
        return
    except ValueError as exc:
        emit("room_error", {"error": str(exc)})
        return

    emit("room_state", created, to=code)


@socketio.on("room_move")
def on_room_move(payload):
    data = payload or {}
    code = str(data.get("code", "")).upper().strip()
    try:
        row = int(data.get("row", -1))
        col = int(data.get("col", -1))
    except (TypeError, ValueError):
        emit("room_error", {"error": "Nuoc di khong hop le"})
        return
    context = CONNECTED_USERS.get(request.sid)
    user_id = int(context["user_id"]) if context else 0

    updated = online_service.process_online_move(code, user_id, row, col)
    if not updated:
        emit("room_error", {"error": "Nuoc di khong hop le"})
        return

    emit("room_state", updated, to=code)


@socketio.on("room_chat")
def on_room_chat(payload):
    data = payload or {}
    code = str(data.get("code", "")).upper().strip()
    message = str(data.get("message", ""))
    context = CONNECTED_USERS.get(request.sid)
    user_id = int(context["user_id"]) if context else 0

    try:
        item = online_service.add_chat_message(code, user_id, message)
        if not item:
            emit("room_error", {"error": "Gui tin nhan that bai"})
            return
    except (PermissionError, ValueError) as exc:
        emit("room_error", {"error": str(exc)})
        return

    emit("room_chat_message", item, to=code)


@socketio.on("room_owner_mute")
def on_room_owner_mute(payload):
    data = payload or {}
    code = str(data.get("code", "")).upper().strip()
    try:
        target_user_id = int(data.get("targetUserId", 0))
    except (TypeError, ValueError):
        emit("room_error", {"error": "Target user khong hop le"})
        return
    muted = bool(data.get("muted", True))
    context = CONNECTED_USERS.get(request.sid)
    owner_user_id = int(context["user_id"]) if context else 0

    try:
        updated_room = online_service.owner_set_mute(code, owner_user_id, target_user_id, muted)
        if not updated_room:
            emit("room_error", {"error": "Cap nhat mute that bai"})
            return
    except (PermissionError, ValueError) as exc:
        emit("room_error", {"error": str(exc)})
        return

    emit("room_state", {"room": updated_room}, to=code)


@socketio.on("room_owner_set_cohost")
def on_room_owner_set_cohost(payload):
    data = payload or {}
    code = str(data.get("code", "")).upper().strip()
    try:
        target_user_id = int(data.get("targetUserId", 0))
    except (TypeError, ValueError):
        emit("room_error", {"error": "Target user khong hop le"})
        return
    enabled = bool(data.get("enabled", True))
    context = CONNECTED_USERS.get(request.sid)
    owner_user_id = int(context["user_id"]) if context else 0

    try:
        updated_room = online_service.owner_set_cohost(code, owner_user_id, target_user_id, enabled)
        if not updated_room:
            emit("room_error", {"error": "Cap nhat co-host that bai"})
            return
    except (PermissionError, ValueError) as exc:
        emit("room_error", {"error": str(exc)})
        return

    emit("room_state", {"room": updated_room}, to=code)


@socketio.on("room_owner_kick")
def on_room_owner_kick(payload):
    data = payload or {}
    code = str(data.get("code", "")).upper().strip()
    try:
        target_user_id = int(data.get("targetUserId", 0))
    except (TypeError, ValueError):
        emit("room_error", {"error": "Target user khong hop le"})
        return
    context = CONNECTED_USERS.get(request.sid)
    owner_user_id = int(context["user_id"]) if context else 0

    try:
        result = online_service.owner_kick_member(code, owner_user_id, target_user_id)
        if not result:
            emit("room_error", {"error": "Kick that bai"})
            return
    except (PermissionError, ValueError) as exc:
        emit("room_error", {"error": str(exc)})
        return

    updated_room = result["room"] if isinstance(result, dict) and "room" in result else result
    system_message = result.get("systemMessage") if isinstance(result, dict) else None

    for sid in USER_SOCKETS.get(target_user_id, set()):
        leave_room(code, sid=sid)
        emit("room_kicked", {"code": code, "message": "Ban da bi chu phong kick"}, to=sid)

    payload = {"room": updated_room}
    updated_state = online_service.get_room_match_state(code)
    if updated_state:
        payload["state"] = updated_state

    emit("room_state", payload, to=code)
    if system_message:
        _emit_system_chat(code, system_message)


@socketio.on("room_owner_transfer")
def on_room_owner_transfer(payload):
    data = payload or {}
    code = str(data.get("code", "")).upper().strip()
    try:
        target_user_id = int(data.get("targetUserId", 0))
    except (TypeError, ValueError):
        emit("room_error", {"error": "Target user khong hop le"})
        return

    context = CONNECTED_USERS.get(request.sid)
    owner_user_id = int(context["user_id"]) if context else 0

    try:
        result = online_service.owner_transfer_ownership(code, owner_user_id, target_user_id)
        if not result:
            emit("room_error", {"error": "Chuyen chu phong that bai"})
            return
    except (PermissionError, ValueError) as exc:
        emit("room_error", {"error": str(exc)})
        return

    updated_room = result["room"] if isinstance(result, dict) and "room" in result else result
    emit("room_state", {"room": updated_room}, to=code)

    system_message = result.get("systemMessage") if isinstance(result, dict) else None
    if system_message:
        _emit_system_chat(code, system_message)
