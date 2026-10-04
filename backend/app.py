import logging
import os

import pymysql
from flask import Flask, jsonify
from flask_cors import CORS

import auth
import config
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp
from routes.browse_routes import browse_bp
from routes.notes_routes import notes_bp


def configure_logging():
    level = logging.INFO if config.IS_PRODUCTION else logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


configure_logging()
log = logging.getLogger(__name__)

app = Flask(__name__)
app.config.update(
    DEBUG=config.DEBUG and not config.IS_PRODUCTION,
    TESTING=False,
)
CORS(app, origins=config.CORS_ORIGINS)

# Reject oversized request bodies (the upload limit plus room for the form fields).
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_BYTES + 64 * 1024

# Fail closed if production was started without an explicit frontend origin.
if config.IS_PRODUCTION and not config.CORS_ORIGINS:
    raise RuntimeError("CORS_ALLOWED_ORIGINS must be set in production")

# Ensure the configured upload directory exists. Persistence itself depends on
# the deployment platform's storage configuration.
config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app.register_blueprint(auth_bp)
app.register_blueprint(browse_bp)
app.register_blueprint(notes_bp)
app.register_blueprint(admin_bp)

app.register_error_handler(auth.AuthError, auth.handle_auth_error)
app.register_error_handler(auth.ConfigError, auth.handle_config_error)


@app.errorhandler(400)
def handle_bad_request(err):
    return jsonify({"error": "Bad request"}), 400


@app.errorhandler(404)
def handle_not_found(err):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(405)
def handle_method_not_allowed(err):
    return jsonify({"error": "Method not allowed"}), 405


@app.errorhandler(413)
def handle_too_large(err):
    limit_mb = config.MAX_UPLOAD_BYTES // (1024 * 1024)
    return jsonify({"error": f"File is too large (maximum {limit_mb} MB)"}), 413


@app.errorhandler(pymysql.MySQLError)
def handle_db_error(err):
    log.exception("Database error")
    return jsonify({"error": "Database unavailable"}), 503


@app.errorhandler(500)
def handle_internal_error(err):
    log.exception("Unhandled application error")
    return jsonify({"error": "Internal server error"}), 500


@app.get("/ping")
def ping():
    return jsonify({"message": "CampusNotes API is running"})


log.info(
    "CampusNotes API starting: environment=%s debug=%s upload_directory=%s",
    config.FLASK_ENV,
    app.debug,
    config.UPLOADS_DIR,
)

if __name__ == "__main__":
    # Local development entry point only. Production must use a WSGI server.
    app.run(host=os.environ.get("FLASK_HOST", "127.0.0.1"),
            port=int(os.environ.get("FLASK_PORT", "5000")),
            debug=app.debug)
