"""MySQL connection helper using PyMySQL (no ORM)."""
import pymysql
from pymysql.cursors import DictCursor

import config


def get_connection():
    """Open a new connection to the CampusNotes database."""
    return pymysql.connect(
        host=config.DATABASE_HOST,
        port=config.DATABASE_PORT,
        user=config.DATABASE_USER,
        password=config.DATABASE_PASSWORD,
        database=config.DATABASE_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
    )

