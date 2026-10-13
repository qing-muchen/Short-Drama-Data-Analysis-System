"""CLI for an explicit check/apply of the reviewed DQ Rules 1.0 seed."""

from __future__ import annotations

import argparse
from datetime import datetime
import json

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from config.settings import get_settings
from services.data_quality_rule_seed import seed_data_quality_rules


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-database",
        required=True,
        help="Exact configured database name; prevents accidental cross-environment writes.",
    )
    parser.add_argument(
        "--valid-from",
        required=True,
        help="Approved UTC-naive ISO datetime at which rule version 1.0 becomes effective.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Insert missing rules in one transaction; default mode is read-only check.",
    )
    parser.add_argument(
        "--actor-user-id",
        type=int,
        help="Existing administrator user ID recorded in the audit log; required with --apply.",
    )
    args = parser.parse_args()

    database_url = get_settings().database_url
    actual_database = make_url(database_url).database
    if actual_database != args.expected_database:
        parser.error("configured database does not match --expected-database")
    valid_from = datetime.fromisoformat(args.valid_from)
    if valid_from.tzinfo is not None and valid_from.utcoffset() is not None:
        parser.error("--valid-from must be UTC-naive to match MySQL DATETIME storage")
    if args.apply and (args.actor_user_id is None or args.actor_user_id < 1):
        parser.error("--actor-user-id is required with --apply")

    engine = create_engine(database_url, pool_pre_ping=True)
    with Session(engine) as session:
        result = seed_data_quality_rules(
            session,
            valid_from=valid_from,
            apply=args.apply,
            actor_user_id=args.actor_user_id,
        )
    print(
        json.dumps(
            {
                "database": actual_database,
                "mode": result.mode,
                "inserted_count": result.inserted_count,
                "unchanged_count": result.unchanged_count,
                "configuration_hash": result.configuration_hash,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
