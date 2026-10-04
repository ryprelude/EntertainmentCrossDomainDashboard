"""Validate all inputs, then replace the local database with a complete snapshot."""

import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile

import pandas as pd

from src.settings import DB_PATH, RAW_DIR, SCHEMAS
from src.validate import passed, print_report, read_csvs, validate_tables


def load_data(raw_dir=RAW_DIR, db_path=DB_PATH):
    tables = read_csvs(raw_dir)
    report = validate_tables(tables)
    print_report(report)
    if not passed(report):
        raise ValueError("Validation failed; the existing database was not changed.")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Write a separate file first, so an interrupted load leaves the old DB intact.
    with tempfile.NamedTemporaryFile(dir=db_path.parent, suffix=".tmp", delete=False) as file:
        temporary_path = Path(file.name)
    try:
        with closing(sqlite3.connect(temporary_path)) as connection:
            for name, frame in tables.items():
                for column in SCHEMAS[name]["numbers"]:
                    frame[column] = pd.to_numeric(frame[column]).astype("int64")
                frame.to_sql(name, connection, index=False, if_exists="fail")
                # Table/column names come only from the fixed schema, not user input.
                keys = ", ".join(SCHEMAS[name]["key"])
                connection.execute(f"CREATE UNIQUE INDEX idx_{name}_key ON {name} ({keys})")
            connection.commit()
        temporary_path.replace(db_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"[LOADED] {sum(len(frame) for frame in tables.values())} rows into {db_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--db-path", type=Path, default=DB_PATH)
    args = parser.parse_args()
    try:
        load_data(args.raw_dir, args.db_path)
    except (OSError, ValueError, sqlite3.Error, pd.errors.ParserError) as error:
        print(f"[FAIL] {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
