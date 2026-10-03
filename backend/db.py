"""MySQL connection helper using PyMySQL (no ORM)."""
import pymysql
from pymysql.cursors import DictCursor

import config


def get_connection():
    """Open a new connection to the CampusNotes database.

    Rows are returned as dictionaries. Autocommit is off, so callers must call
    connection.commit() after writes. Callers are responsible for closing it.
    """
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
    )
