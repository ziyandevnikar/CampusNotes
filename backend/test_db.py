"""Database connection test. Run from backend/ after loading init.sql:

    python test_db.py
"""
import sys

import pymysql

from db import get_connection

TABLES = ["users", "courses", "semesters", "subjects", "units", "notes"]
EXPECTED_FKS = {
    ("semesters", "courses"),
    ("subjects", "semesters"),
    ("units", "subjects"),
    ("notes", "units"),
    ("notes", "users"),
}
MIN_ROWS = {"users": 2, "courses": 1, "semesters": 2, "subjects": 2, "units": 2, "notes": 3}

failures = []


def check(label, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(label)


def main():
    try:
        conn = get_connection()
    except Exception as exc:
        print(f"[FAIL] Cannot connect to MySQL: {exc}")
        sys.exit(1)
    check("Connected to MySQL through db.py", True)

    with conn.cursor() as cur:
        cur.execute("SELECT DATABASE() AS db")
        check("Connected to database 'campusnotes'", cur.fetchone()["db"] == "campusnotes")

        cur.execute("SHOW TABLES")
        found = {list(row.values())[0] for row in cur.fetchall()}
        check("Exactly the six tables exist", found == set(TABLES), f"found: {sorted(found)}")

        cur.execute(
            "SELECT TABLE_NAME AS t, REFERENCED_TABLE_NAME AS r "
            "FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL"
        )
        fks = {(row["t"], row["r"]) for row in cur.fetchall()}
        check("All 5 foreign keys are defined", fks == EXPECTED_FKS, f"found: {sorted(fks)}")

        for table, minimum in MIN_ROWS.items():
            cur.execute(f"SELECT COUNT(*) AS n FROM {table}")
            n = cur.fetchone()["n"]
            check(f"Seed data in {table}", n >= minimum, f"{n} rows")

        cur.execute("SELECT role FROM users ORDER BY role")
        roles = [row["role"] for row in cur.fetchall()]
        check("Seed has an admin and a student", "admin" in roles and "student" in roles)

        cur.execute("SELECT status, COUNT(*) AS n FROM notes GROUP BY status")
        statuses = {row["status"] for row in cur.fetchall()}
        check("Seed notes include approved, pending and rejected", statuses == {"approved", "pending", "rejected"})

        # Foreign keys must be enforced: a note pointing at a missing unit/uploader must fail.
        try:
            cur.execute(
                "INSERT INTO notes (title, unit_id, uploader_id, file_path) "
                "VALUES ('fk test', 99999, 1, 'x.pdf')"
            )
            check("FK rejects note with non-existent unit_id", False)
        except pymysql.err.IntegrityError:
            check("FK rejects note with non-existent unit_id", True)
        try:
            cur.execute(
                "INSERT INTO notes (title, unit_id, uploader_id, file_path) "
                "VALUES ('fk test', 1, 99999, 'x.pdf')"
            )
            check("FK rejects note with non-existent uploader_id", False)
        except pymysql.err.IntegrityError:
            check("FK rejects note with non-existent uploader_id", True)

        # Unique email.
        try:
            cur.execute(
                "INSERT INTO users (name, email, password_hash) "
                "VALUES ('dup', 'admin@campusnotes.demo', 'x')"
            )
            check("Duplicate email is rejected", False)
        except pymysql.err.IntegrityError:
            check("Duplicate email is rejected", True)

        # Defaults, inside a transaction that is rolled back.
        cur.execute(
            "INSERT INTO notes (title, unit_id, uploader_id, file_path) "
            "VALUES ('default test', 1, 2, 'x.pdf')"
        )
        cur.execute("SELECT status, download_count, created_at FROM notes WHERE id = LAST_INSERT_ID()")
        row = cur.fetchone()
        check(
            "Defaults: status=pending, download_count=0, created_at set",
            row["status"] == "pending" and row["download_count"] == 0 and row["created_at"] is not None,
        )

    conn.rollback()  # discard every test insert
    conn.close()

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED")
        sys.exit(1)
    print("All checks passed")


if __name__ == "__main__":
    main()
