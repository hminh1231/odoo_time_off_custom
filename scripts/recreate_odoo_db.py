"""Recreate empty odoo_db for a clean Odoo 19 install (no data kept)."""
import sys

import psycopg2

CONN = dict(host="localhost", port=5432, user="odoo_user", password="121096")


def main():
    try:
        conn = psycopg2.connect(dbname="postgres", **CONN)
    except Exception as e:
        print("Cannot connect to PostgreSQL as odoo_user on database 'postgres':", e)
        print("Create the new DB manually in pgAdmin or fix credentials.")
        sys.exit(1)

    conn.autocommit = True
    cr = conn.cursor()

    cr.execute("SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user")
    row = cr.fetchone()
    if not row or not row[0]:
        print("User odoo_user cannot CREATE DATABASE. Use a superuser (postgres) to run:")
        print('  DROP DATABASE IF EXISTS odoo_db;')
        print("  CREATE DATABASE odoo_db WITH ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0;")
        print("  GRANT ALL ON DATABASE odoo_db TO odoo_user;")
        conn.close()
        sys.exit(1)

    cr.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'odoo_db' AND pid <> pg_backend_pid()")
    cr.execute("DROP DATABASE IF EXISTS odoo_db")
    print("Dropped old odoo_db.")
    # C locale avoids Windows collation issues on some PostgreSQL builds.
    cr.execute(
        """
        CREATE DATABASE odoo_db
        WITH OWNER odoo_user
        ENCODING 'UTF8'
        LC_COLLATE 'C'
        LC_CTYPE 'C'
        TEMPLATE template0
        """
    )
    print("Created fresh empty odoo_db.")
    conn.close()


if __name__ == "__main__":
    main()
