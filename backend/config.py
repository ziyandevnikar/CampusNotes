"""Application settings. Secrets come from environment variables, never from code."""
import os

# Origin of the Angular dev server. Flask-CORS allows requests from here.
CORS_ORIGINS = ["http://localhost:4200"]

# MySQL connection settings (see .env.example)
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "campusnotes")

# JWT settings. JWT_SECRET has no default on purpose: login fails with a
# server error until it is set.
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
