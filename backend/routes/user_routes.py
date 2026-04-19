from flask import Blueprint, jsonify, request

from backend.controllers.user_controller import (
    achievements,
    chat_filter_settings,
    claim_all_mail,
    claim_mail,
    equip_item,
    inventory,
    leaderboard,
    login,
    mailbox,
    match_history,
    match_replay,
    me,
    public_profile,
    rank_catalog,
    register,
    update_chat_filter_settings,
    update_profile,
)

user_blueprint = Blueprint("user", __name__)


def _bearer_token() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


@user_blueprint.post("/register")
def register_route():
    payload = request.get_json(silent=True) or {}
    body, status = register(payload)
    return jsonify(body), status


@user_blueprint.post("/login")
def login_route():
    payload = request.get_json(silent=True) or {}
    body, status = login(payload)
    return jsonify(body), status


@user_blueprint.get("/me")
def me_route():
    body, status = me(_bearer_token())
    return jsonify(body), status


@user_blueprint.get("/leaderboard")
def leaderboard_route():
    limit = int(request.args.get("limit", "20"))
    kind = str(request.args.get("kind", "room"))
    body, status = leaderboard(limit, kind)
    return jsonify(body), status


@user_blueprint.get("/achievements")
def achievements_route():
    body, status = achievements(_bearer_token())
    return jsonify(body), status


@user_blueprint.patch("/profile")
def update_profile_route():
    payload = request.get_json(silent=True) or {}
    body, status = update_profile(payload, _bearer_token())
    return jsonify(body), status


@user_blueprint.get("/public/<int:user_id>")
def public_profile_route(user_id: int):
    raw_rank_pos = request.args.get("rankPos", "").strip()
    rank_pos = int(raw_rank_pos) if raw_rank_pos.isdigit() else None
    body, status = public_profile(user_id, rank_position=rank_pos)
    return jsonify(body), status


@user_blueprint.get("/mailbox")
def mailbox_route():
    body, status = mailbox(_bearer_token())
    return jsonify(body), status


@user_blueprint.get("/matches")
def match_history_route():
    raw_limit = str(request.args.get("limit", "30")).strip()
    limit = int(raw_limit) if raw_limit.isdigit() else 30
    body, status = match_history(_bearer_token(), limit=limit)
    return jsonify(body), status


@user_blueprint.get("/matches/<int:match_id>/replay")
def match_replay_route(match_id: int):
    body, status = match_replay(match_id, _bearer_token())
    return jsonify(body), status


@user_blueprint.post("/mailbox/<int:mail_id>/claim")
def claim_mail_route(mail_id: int):
    body, status = claim_mail(mail_id, _bearer_token())
    return jsonify(body), status


@user_blueprint.post("/mailbox/claim-all")
def claim_all_mail_route():
    body, status = claim_all_mail(_bearer_token())
    return jsonify(body), status


@user_blueprint.get("/inventory")
def inventory_route():
    body, status = inventory(_bearer_token())
    return jsonify(body), status


@user_blueprint.post("/inventory/equip")
def equip_item_route():
    payload = request.get_json(silent=True) or {}
    body, status = equip_item(payload, _bearer_token())
    return jsonify(body), status


@user_blueprint.get("/rank-catalog")
def rank_catalog_route():
    body, status = rank_catalog()
    return jsonify(body), status


@user_blueprint.get("/chat-filter")
def chat_filter_route():
    body, status = chat_filter_settings(_bearer_token())
    return jsonify(body), status


@user_blueprint.patch("/chat-filter")
def update_chat_filter_route():
    payload = request.get_json(silent=True) or {}
    body, status = update_chat_filter_settings(payload, _bearer_token())
    return jsonify(body), status


@user_blueprint.get("/health")
def health():
    return jsonify({"status": "ok"}), 200
