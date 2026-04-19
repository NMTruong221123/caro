import uuid

from backend.controllers.game_controller import play_move, start_new_match
from backend.server import create_app
from backend.services import auth_service, db_service


create_app()


def _make_user_and_token() -> tuple[dict, str]:
    username = f"ai_learn_{uuid.uuid4().hex[:8]}"
    user = auth_service.register_user(username, "123456")
    if user is None:
        loaded = db_service.get_user_by_username(username)
        assert loaded is not None
        user = loaded
    session = auth_service.login_user(username, "123456")
    assert session is not None
    return user, str(session["token"])


def test_ai_learning_heatmap_updates_after_human_move():
    _user, token = _make_user_and_token()

    state, status = start_new_match(
        {
            "mode": "ai",
            "boardSize": 9,
            "winLength": 5,
            "aiLevel": "medium",
        },
        token,
    )
    assert status == 201

    move_resp, move_status = play_move(
        {
            "matchId": state["matchId"],
            "row": 4,
            "col": 4,
        },
        token,
    )
    assert move_status == 200
    assert move_resp["status"] in {"playing", "finished", "draw"}

    heat = db_service.get_ai_heatmap(9)
    assert int(heat.get((4, 4), 0)) >= 1
