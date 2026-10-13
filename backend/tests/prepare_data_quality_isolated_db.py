"""Clone schema-only metadata into a guarded Data Quality isolation database."""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from config.settings import get_settings

PREFIX = "short_drama_s5_2_b2_part1_"
PROTECTED = {
    "short_drama_analysis",
    "short_drama_acceptance_v1",
    "short_drama_analysis_test",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate only the explicitly named guarded isolation database.",
    )
    args = parser.parse_args()
    target_name = args.database
    if not target_name.startswith(PREFIX) or target_name in PROTECTED:
        parser.error(f"database must start with {PREFIX!r} and not be protected")

    source_url = make_url(get_settings().database_url)
    source_name = source_url.database
    if source_name != "short_drama_analysis":
        parser.error("configured source must be the read-only development schema")
    admin_url = source_url.set(database=None)
    target_url = source_url.set(database=target_name)
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    source = create_engine(source_url)
    try:
        with admin.connect() as connection:
            exists = bool(
                connection.scalar(
                    text(
                        "SELECT COUNT(*) FROM information_schema.schemata "
                        "WHERE schema_name = :name"
                    ),
                    {"name": target_name},
                )
            )
            if exists and not args.recreate:
                parser.error("isolation database exists; pass --recreate explicitly")
            if exists:
                connection.execute(text(f"DROP DATABASE `{target_name}`"))
            connection.execute(
                text(
                    f"CREATE DATABASE `{target_name}` CHARACTER SET utf8mb4 "
                    "COLLATE utf8mb4_0900_ai_ci"
                )
            )

        with source.connect() as source_connection:
            table_names = tuple(
                row[0]
                for row in source_connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = :schema AND table_type = 'BASE TABLE' "
                        "ORDER BY table_name"
                    ),
                    {"schema": source_name},
                ).all()
            )
            definitions = tuple(
                source_connection.execute(
                    text(f"SHOW CREATE TABLE `{table_name}`")
                ).one()[1]
                for table_name in table_names
            )

        target = create_engine(target_url, isolation_level="AUTOCOMMIT")
        try:
            with target.connect() as target_connection:
                target_connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                for definition in definitions:
                    target_connection.exec_driver_sql(definition)
                target_connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        finally:
            target.dispose()
    finally:
        source.dispose()
        admin.dispose()
    print(f"prepared {target_name}: {len(definitions)} tables, 0 copied rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
