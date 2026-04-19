from flask import Blueprint, jsonify, request

from backend.controllers.online_controller import active_room_session, create_room, join_room, room_detail

online_blueprint = Blueprint("online", __name__)


def _bearer_token() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


@online_blueprint.post("/room/create")
def create_room_route():
    payload = request.get_json(silent=True) or {}
    body, status = create_room(payload, _bearer_token())
    return jsonify(body), status


@online_blueprint.post("/room/join")
def join_room_route():
    payload = request.get_json(silent=True) or {}
    body, status = join_room(payload, _bearer_token())
    return jsonify(body), status


@online_blueprint.get("/room/<string:code>")
def room_detail_route(code: str):
    body, status = room_detail(code, _bearer_token())
    return jsonify(body), status


@online_blueprint.get("/room/active")
def active_room_route():
    body, status = active_room_session(_bearer_token())
    return jsonify(body), status
