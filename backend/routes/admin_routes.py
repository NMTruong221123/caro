from flask import Blueprint, jsonify, request

from backend.controllers.admin_controller import dashboard_summary, update_chat_filter


admin_blueprint = Blueprint("admin", __name__)


def _admin_token() -> str:
    return str(request.headers.get("X-Admin-Token", ""))


def _bearer_token() -> str:
    auth = str(request.headers.get("Authorization", ""))
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


@admin_blueprint.get("/summary")
def summary_route():
    body, status = dashboard_summary(_admin_token(), user_token=_bearer_token())
    return jsonify(body), status


@admin_blueprint.patch("/chat-filter")
def update_chat_filter_route():
    payload = request.get_json(silent=True) or {}
    body, status = update_chat_filter(_admin_token(), payload, user_token=_bearer_token())
    return jsonify(body), status
