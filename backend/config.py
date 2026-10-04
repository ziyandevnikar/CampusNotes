"""Application settings loaded from environment variables.

Development defaults are intentionally local-only. Production deployments must
provide database credentials, JWT_SECRET, and CORS_ALLOWED_ORIGINS through the
environment.
"""
import os
from pathlib import Path


def _env_int(name, default):
    value = os.environ.get(name, str(default))
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def _split_origins(value):
    return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]


# Deployment environment. Flask 3 no longer uses FLASK_ENV to toggle debug,
# so the application reads it explicitly as an equivalent configuration flag.
FLASK_ENV = os.environ.get("FLASK_ENV", "development").strip().lower()
IS_PRODUCTION = FLASK_ENV == "production"
DEBUG = os.environ.get("FLASK_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}

# CORS: localhost is a development-only default. Production must explicitly
# provide the deployed frontend origin(s), comma-separated.
_cors_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "")
CORS_ORIGINS = _split_origins(_cors_raw) if _cors_raw else (
    ["http://localhost:4200"] if not IS_PRODUCTION else []
)

# MySQL connection settings. DATABASE_* are the production names. DB_* aliases
# are retained only for backwards compatibility with existing local test setup.
DATABASE_HOST = os.environ.get("DATABASE_HOST", os.environ.get("DB_HOST", "localhost"))
DATABASE_PORT = _env_int("DATABASE_PORT", os.environ.get("DB_PORT", "3306"))
DATABASE_USER = os.environ.get("DATABASE_USER", os.environ.get("DB_USER", "root"))
DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD", os.environ.get("DB_PASSWORD", ""))
DATABASE_NAME = os.environ.get("DATABASE_NAME", os.environ.get("DB_NAME", "campusnotes"))

# Backwards-compatible names used by the Stage 8 tests/modules.
DB_HOST = DATABASE_HOST
DB_PORT = DATABASE_PORT
DB_USER = DATABASE_USER
DB_PASSWORD = DATABASE_PASSWORD
DB_NAME = DATABASE_NAME

# JWT settings. JWT_SECRET has no default on purpose.
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = _env_int("JWT_EXPIRY_HOURS", 24)

BASE_DIR = Path(__file__).resolve().parent
SEED_FILES_DIR = BASE_DIR / "seed_files"

# UPLOAD_DIRECTORY may be absolute or relative to backend/. A persistent disk
# mount can therefore be supplied by the deployment platform without changing
# application code or database schema.
_upload_directory = os.environ.get("UPLOAD_DIRECTORY", "uploads")
UPLOADS_DIR = Path(_upload_directory)
if not UPLOADS_DIR.is_absolute():
    UPLOADS_DIR = BASE_DIR / UPLOADS_DIR
UPLOADS_DIR = UPLOADS_DIR.resolve()

# Largest PDF a student may upload (bytes).
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
