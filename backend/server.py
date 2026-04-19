import mimetypes
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from backend.routes.admin_routes import admin_blueprint
from backend.routes.game_routes import game_blueprint
from backend.routes.online_routes import online_blueprint
from backend.routes.user_routes import user_blueprint
from backend.services.db_service import init_db_if_missing
from backend.services.admin_service import record_runtime_error
from backend.services.socket_service import socketio


mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(ROOT_DIR / "frontend"),
        static_url_path="",
    )

    init_db_if_missing()
    socketio.init_app(app)

    app.register_blueprint(game_blueprint, url_prefix="/api/game")
    app.register_blueprint(user_blueprint, url_prefix="/api/user")
    app.register_blueprint(online_blueprint, url_prefix="/api/online")
    app.register_blueprint(admin_blueprint, url_prefix="/api/admin")

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error

        record_runtime_error("flask", str(error))
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        raise error

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    return app


application = create_app()


if __name__ == "__main__":
    host = str(os.getenv("HOST", "0.0.0.0")).strip() or "0.0.0.0"
    port = int(str(os.getenv("PORT", "5000")).strip() or "5000")
    debug = str(os.getenv("FLASK_DEBUG", "0")).strip().lower() in {"1", "true", "yes", "on"}
    socketio.run(application, host=host, port=port, debug=debug)
