"""Validate without silently dropping, filling, or correcting source rows."""

import argparse
import math
from pathlib import Path

import pandas as pd

from src.settings import RAW_DIR, SCHEMAS


def read_csvs(raw_dir=RAW_DIR):
    # Keep identifiers and date strings exactly as supplied until validation.
    return {name: pd.read_csv(Path(raw_dir) / f"{name}.csv", dtype="string")
            for name in SCHEMAS}


def validate_tables(tables):
    results = []

    def record(table, check, issues):
        results.append({"table": table, "check": check,
                        "status": "PASS" if issues == 0 else "FAIL", "issues": int(issues)})

    for name, schema in SCHEMAS.items():
        if name not in tables:
            record(name, "required table", 1)
            continue
        frame = tables[name]
        wrong_columns = set(schema["columns"]) ^ set(frame.columns)
        record(name, "expected columns", len(wrong_columns))
        if wrong_columns:
            continue

        # Empty fact tables are valid (e.g. a company with no events yet).
        if name == "contents":
            record(name, "non-empty content catalog", int(frame.empty))
        missing_count = frame.isna().sum().sum()
        blank_count = sum(frame[col].astype("string").str.strip().eq("").sum() for col in frame)
        record(name, "missing or blank values", missing_count + blank_count)
        record(name, "duplicate rows", frame.duplicated().sum())
        record(name, "duplicate business keys", frame.duplicated(schema["key"]).sum())
        identifiers = frame["content_id"].astype("string")
        record(name, "content_id whitespace", identifiers.ne(identifiers.str.strip()).sum())

        for column in schema["numbers"]:
            values = pd.to_numeric(frame[column], errors="coerce")
            finite = values.map(lambda value: pd.notna(value) and math.isfinite(value))
            record(name, f"{column}: finite numeric values", (~finite).sum())
            record(name, f"{column}: non-negative", (values < 0).sum())
            # Counts, whole JPY and rounded watch hours are integers in this mock model.
            valid_integer = finite & values.ge(0) & values.lt(2**63) & values.mod(1).eq(0)
            record(name, f"{column}: SQLite-safe non-negative integer", (~valid_integer).sum())

        for column, date_format in schema["dates"].items():
            text = frame[column].astype("string")
            parsed = pd.to_datetime(text, format=date_format, errors="coerce")
            # Round-trip enforces YYYY-MM / YYYY-MM-DD, including leading zeroes.
            valid = parsed.notna() & parsed.dt.strftime(date_format).eq(text)
            record(name, f"{column}: {date_format}", (~valid.fillna(False)).sum())

        if name != "contents":
            master = tables.get("contents")
            if master is None or "content_id" not in master:
                record(name, "content_id reference unavailable", 1)
            else:
                record(name, "content_id reference", (~frame["content_id"].isin(master["content_id"])).sum())
    return results


def passed(results):
    return bool(results) and all(row["status"] == "PASS" for row in results)


def print_report(results):
    for row in results:
        print(f'[{row["status"]}] {row["table"]}.{row["check"]}: {row["issues"]} issue(s)')
    print("Validation passed." if passed(results) else "Validation failed. Fix the source CSVs before loading.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    try:
        results = validate_tables(read_csvs(args.raw_dir))
    except (OSError, ValueError, pd.errors.ParserError) as error:
        print(f"[FAIL] Could not read CSVs: {error}")
        return 1
    print_report(results)
    return 0 if passed(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
