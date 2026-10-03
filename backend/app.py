import logging

import pymysql
from flask import Flask, jsonify
from flask_cors import CORS

import auth
import config
from routes.auth_routes import auth_bp

app = Flask(__name__)
CORS(app, origins=config.CORS_ORIGINS)

app.register_blueprint(auth_bp)

app.register_error_handler(auth.AuthError, auth.handle_auth_error)
app.register_error_handler(auth.ConfigError, auth.handle_config_error)


@app.errorhandler(pymysql.MySQLError)
def handle_db_error(err):
    logging.getLogger(__name__).exception("Database error")
    return jsonify({"error": "Database unavailable"}), 503


@app.get("/ping")
def ping():
    return jsonify({"message": "CampusNotes API is running"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
