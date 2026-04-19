import uuid

from backend.server import create_app
from backend.services import auth_service, db_service, online_service


create_app()


def _user(prefix: str) -> dict:
    username = f"{prefix}_{uuid.uuid4().hex[:8]}"
    created = auth_service.register_user(username, "123456")
    if created:
        return created
    loaded = db_service.get_user_by_username(username)
    assert loaded is not None
    return loaded


def _reset_queue_state() -> None:
    online_service._RANK_QUEUE.clear()  # type: ignore[attr-defined]
    online_service._RANK_QUEUE_META.clear()  # type: ignore[attr-defined]


def test_rank_queue_prevents_multi_tab_same_user():
    _reset_queue_state()
    user = _user("rank_tab")

    first = online_service.rank_queue_join(int(user["id"]), "sid-1")
    second = online_service.rank_queue_join(int(user["id"]), "sid-2")

    assert first.get("matched") is False
    assert second.get("reason") == "already_searching_another_tab"


def test_rank_queue_cancel_and_timeout(monkeypatch):
    _reset_queue_state()
    u1 = _user("rank_cancel")
    u2 = _user("rank_timeout")

    online_service.rank_queue_join(int(u1["id"]), "sid-a")
    canceled = online_service.rank_queue_cancel(int(u1["id"]), sid="sid-a")
    assert canceled.get("removed") is True

    online_service.rank_queue_join(int(u1["id"]), "sid-a")
    joined_at = float(online_service._RANK_QUEUE_META[int(u1["id"])] ["joined_at"])  # type: ignore[attr-defined]
    monkeypatch.setattr(online_service.time, "time", lambda: joined_at + 999)
    result = online_service.rank_queue_join(int(u2["id"]), "sid-b")

    assert int(u1["id"]) in result.get("timedOutUsers", [])
    assert result.get("matched") is False
