import uuid

from backend.server import create_app
from backend.services import auth_service, db_service, online_service


app = create_app()


def _user(prefix: str):
    username = f"{prefix}_{uuid.uuid4().hex[:8]}"
    user = auth_service.register_user(username, "123456")
    if user:
        return user
    loaded = db_service.get_user_by_username(username)
    assert loaded is not None
    return loaded


def _token(username: str) -> str:
    session = auth_service.login_user(username, "123456")
    assert session is not None
    return str(session["token"])


def test_active_room_session_for_reconnect():
    client = app.test_client()

    owner = _user("reconnect_owner")
    guest = _user("reconnect_guest")
    owner_token = _token(owner["username"])
    guest_token = _token(guest["username"])

    room = online_service.create_room(int(owner["id"]), 2)
    code = str(room["code"])
    online_service.join_room(code, int(guest["id"]))
    started = online_service.start_room_game(code, int(owner["id"]), 15, 5)
    assert started is not None

    response = client.get(
        "/api/online/room/active",
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    body = response.get_json()

    assert response.status_code == 200
    assert body["session"] is not None
    assert body["session"]["room"]["code"] == code
    assert body["session"]["state"]["status"] in {"playing", "finished", "draw"}

    _ = owner_token


def test_match_history_and_replay_endpoint():
    client = app.test_client()

    p1 = _user("history_p1")
    p2 = _user("history_p2")
    p1_token = _token(p1["username"])

    room = online_service.create_room(int(p1["id"]), 2, room_type="ranked")
    code = str(room["code"])
    online_service.join_room(code, int(p2["id"]))
    started = online_service.start_room_game(code, int(p1["id"]), 15, 5, match_type="ranked")
    assert started is not None

    _ = online_service.process_online_move(code, int(p1["id"]), 7, 7)

    history_resp = client.get(
        "/api/user/matches?limit=10",
        headers={"Authorization": f"Bearer {p1_token}"},
    )
    history_body = history_resp.get_json()
    assert history_resp.status_code == 200
    assert len(history_body["items"]) >= 1

    match_id = int(history_body["items"][0]["id"])
    replay_resp = client.get(
        f"/api/user/matches/{match_id}/replay",
        headers={"Authorization": f"Bearer {p1_token}"},
    )
    replay_body = replay_resp.get_json()

    assert replay_resp.status_code == 200
    assert replay_body["replay"]["matchId"] == match_id
    assert len(replay_body["replay"]["participants"]) >= 1
    assert isinstance(replay_body["replay"]["moves"], list)


def test_rank_queue_blocks_too_many_accounts_same_ip(monkeypatch):
    online_service._RANK_QUEUE.clear()  # type: ignore[attr-defined]
    online_service._RANK_QUEUE_META.clear()  # type: ignore[attr-defined]
    online_service._RANK_QUEUE_USER_RATE.clear()  # type: ignore[attr-defined]
    online_service._RANK_QUEUE_IP_RATE.clear()  # type: ignore[attr-defined]
    monkeypatch.setattr(online_service, "_can_match_by_stars", lambda _left, _right: False)

    u1 = _user("abuse_ip")
    u2 = _user("abuse_ip")
    u3 = _user("abuse_ip")

    r1 = online_service.rank_queue_join(int(u1["id"]), "sid-abuse-1", ip_address="10.0.0.1")
    r2 = online_service.rank_queue_join(int(u2["id"]), "sid-abuse-2", ip_address="10.0.0.1")
    r3 = online_service.rank_queue_join(int(u3["id"]), "sid-abuse-3", ip_address="10.0.0.1")

    assert r1.get("reason") != "multi_account_suspected"
    assert r2.get("reason") != "multi_account_suspected"
    assert r3.get("reason") == "multi_account_suspected"


def test_admin_summary_requires_token_and_returns_payload():
    client = app.test_client()

    unauthorized = client.get("/api/admin/summary")
    assert unauthorized.status_code == 401

    authorized = client.get(
        "/api/admin/summary",
        headers={"X-Admin-Token": "admin-dev-token"},
    )
    body = authorized.get_json()

    assert authorized.status_code == 200
    assert "stats" in body
    assert "chatFilter" in body
    assert "securityEvents" in body


def test_admin_summary_allows_logged_in_admin_account():
    client = app.test_client()

    admin_session = auth_service.login_user("ADMIN", "123456")
    assert admin_session is not None

    response = client.get(
        "/api/admin/summary",
        headers={"Authorization": f"Bearer {admin_session['token']}"},
    )
    body = response.get_json()

    assert response.status_code == 200
    assert "stats" in body


def test_register_blocks_reserved_admin_username_case_insensitive():
    client = app.test_client()

    response = client.post(
        "/api/user/register",
        json={"username": "admin", "password": "123456"},
    )
    body = response.get_json()

    assert response.status_code == 403
    assert "bao luu" in str(body.get("error", "")).lower()


def test_profile_rename_blocks_reserved_admin_username():
    client = app.test_client()

    user = _user("rename_reserved")
    token = _token(user["username"])
    response = client.patch(
        "/api/user/profile",
        json={"username": "AdMiN"},
        headers={"Authorization": f"Bearer {token}"},
    )
    body = response.get_json()

    assert response.status_code == 403
    assert "bao luu" in str(body.get("error", "")).lower()


def test_register_blocks_case_insensitive_duplicate_username():
    client = app.test_client()

    suffix = uuid.uuid4().hex[:8]
    first_name = f"CaseUser_{suffix}"

    first = client.post(
        "/api/user/register",
        json={"username": first_name, "password": "123456"},
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/api/user/register",
        json={"username": first_name.lower(), "password": "123456"},
    )
    duplicate_body = duplicate.get_json()

    assert duplicate.status_code == 409
    assert "ton tai" in str(duplicate_body.get("error", "")).lower()


def test_login_allows_case_insensitive_username_lookup():
    client = app.test_client()

    suffix = uuid.uuid4().hex[:8]
    mixed_case_username = f"MixCase_{suffix}"
    register = client.post(
        "/api/user/register",
        json={"username": mixed_case_username, "password": "123456"},
    )
    assert register.status_code == 201

    login = client.post(
        "/api/user/login",
        json={"username": mixed_case_username.lower(), "password": "123456"},
    )
    login_body = login.get_json()

    assert login.status_code == 200
    assert str(login_body["user"]["username"]) == mixed_case_username
    assert str(login_body["token"])
