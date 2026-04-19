from flask import Blueprint, jsonify, request

from backend.controllers.game_controller import get_match_state, play_move, start_new_match

game_blueprint = Blueprint("game", __name__)


def _bearer_token() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


@game_blueprint.post("/start")
def start_match_route():
    payload = request.get_json(silent=True) or {}
    body, status = start_new_match(payload, _bearer_token())
    return jsonify(body), status


@game_blueprint.get("/state/<int:match_id>")
def state_route(match_id: int):
    body, status = get_match_state(match_id)
    return jsonify(body), status


@game_blueprint.post("/move")
def move_route():
    payload = request.get_json(silent=True) or {}
    body, status = play_move(payload, _bearer_token())
    return jsonify(body), status
