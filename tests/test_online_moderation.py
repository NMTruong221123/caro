import uuid

from backend.server import create_app
from backend.services import auth_service, db_service, online_service


create_app()


def _ensure_user(prefix: str) -> dict:
    username = f"{prefix}_{uuid.uuid4().hex[:8]}"
    created = auth_service.register_user(username, "123456")
    if created:
        return created
    loaded = db_service.get_user_by_username(username)
    assert loaded is not None
    return loaded


def test_cohost_can_mute_member():
    owner = _ensure_user("owner_cohost")
    cohost = _ensure_user("cohost")
    guest = _ensure_user("guest")

    room = online_service.create_room(int(owner["id"]), 4)
    code = str(room["code"])
    online_service.join_room(code, int(cohost["id"]))
    online_service.join_room(code, int(guest["id"]))

    updated = online_service.owner_set_cohost(code, int(owner["id"]), int(cohost["id"]), True)
    assert updated is not None

    updated = online_service.owner_set_mute(code, int(cohost["id"]), int(guest["id"]), True)
    assert updated is not None
    target = next(item for item in updated["players"] if int(item["user_id"]) == int(guest["id"]))
    assert int(target["is_muted"]) == 1


def test_chat_blocks_vietnamese_obfuscation_and_spam():
    owner = _ensure_user("owner_chat")
    guest = _ensure_user("guest_chat")

    room = online_service.create_room(int(owner["id"]), 2)
    code = str(room["code"])
    online_service.join_room(code, int(guest["id"]))

    # Obfuscated Vietnamese profanity should still be blocked.
    try:
        online_service.add_chat_message(code, int(guest["id"]), "d i t")
        assert False, "Expected banned word filter to block message"
    except ValueError:
        pass

    blocked_spam = False
    for i in range(6):
        try:
            online_service.add_chat_message(code, int(guest["id"]), f"hello-{i}")
        except ValueError:
            blocked_spam = True
            break

    assert blocked_spam is True


def test_kick_during_playing_causes_technical_loss():
    owner = _ensure_user("owner_kick")
    cohost = _ensure_user("cohost_kick")
    guest = _ensure_user("guest_kick")

    room = online_service.create_room(int(owner["id"]), 4)
    code = str(room["code"])
    online_service.join_room(code, int(cohost["id"]))
    online_service.join_room(code, int(guest["id"]))

    online_service.owner_set_cohost(code, int(owner["id"]), int(cohost["id"]), True)
    started = online_service.start_room_game(code, int(owner["id"]), 15, 5)
    assert started is not None
    assert started["state"]["status"] == "playing"

    updated = online_service.owner_kick_member(code, int(cohost["id"]), int(guest["id"]))
    assert updated is not None
    assert isinstance(updated, dict)
    assert "room" in updated
    assert str(updated["room"]["status"]) == "playing"

    match = db_service.get_match(int(started["state"]["matchId"]))
    assert match is not None
    assert str(match["status"]) == "playing"
