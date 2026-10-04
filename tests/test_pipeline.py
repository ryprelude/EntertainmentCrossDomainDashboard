"""Regression checks for data rejection and aggregation correctness."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.analysis import connect_read_only, content_summary, monthly_summary
from src.generate_data import generate_data
from src.load_data import load_data
from src.validate import passed, read_csvs, validate_tables


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raw = Path(self.temp.name) / "raw"
        with contextlib.redirect_stdout(io.StringIO()):
            self.tables = generate_data(self.raw)

    def test_repeatable_generation_and_valid_csvs(self):
        before = {path.name: path.read_bytes() for path in self.raw.glob("*.csv")}
        with contextlib.redirect_stdout(io.StringIO()):
            generate_data(self.raw)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.raw.glob("*.csv")})
        self.assertTrue(passed(validate_tables(read_csvs(self.raw))))

    def test_required_rejections(self):
        for case in ("null", "duplicate", "negative", "unknown_id", "bad_date", "bad_number", "blank"):
            with self.subTest(case=case):
                tables = {name: frame.copy() for name, frame in self.tables.items()}
                if case == "null":
                    tables["contents"].loc[0, "title"] = None
                elif case == "duplicate":
                    tables["streaming"] = pd.concat([tables["streaming"], tables["streaming"].iloc[[0]]])
                elif case == "negative":
                    tables["merchandise"].loc[0, "revenue"] = -1
                elif case == "unknown_id":
                    tables["events"].loc[0, "content_id"] = "UNKNOWN"
                elif case == "bad_date":
                    tables["events"].loc[0, "event_date"] = "2025-02-30"
                elif case == "bad_number":
                    tables["streaming"]["views"] = tables["streaming"]["views"].astype(str)
                    tables["streaming"].loc[0, "views"] = "not a number"
                else:
                    tables["contents"].loc[0, "title"] = "  "
                self.assertFalse(passed(validate_tables(tables)))

    def test_same_key_with_different_values_is_rejected(self):
        extra = self.tables["merchandise"].iloc[[0]].copy()
        extra["revenue"] += 100
        self.tables["merchandise"] = pd.concat([self.tables["merchandise"], extra])
        self.assertFalse(passed(validate_tables(self.tables)))

    def test_empty_event_table_is_allowed(self):
        self.tables["events"] = self.tables["events"].iloc[:0]
        self.assertTrue(passed(validate_tables(self.tables)))


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raw = Path(self.temp.name) / "raw"
        self.db = Path(self.temp.name) / "test.db"
        with contextlib.redirect_stdout(io.StringIO()):
            self.tables = generate_data(self.raw)
            load_data(self.raw, self.db)

    def test_join_totals_match_independent_source_totals(self):
        with contextlib.closing(connect_read_only(self.db)) as connection:
            for start, end in (("2025-01", "2025-12"), ("2025-04", "2025-06")):
                result = content_summary(connection, start, end)
                self.assertEqual(len(result), 8)
                for table, date, value in (("streaming", "month", "views"),
                                           ("merchandise", "month", "revenue"),
                                           ("events", "event_date", "participants")):
                    source = self.tables[table]
                    selected = source[date].str[:7].between(start, end)
                    self.assertEqual(result[value].sum(), source.loc[selected, value].sum())
                no_events = result[result["content_id"].isin(["C007", "C008"])]
                self.assertEqual(no_events["participants"].sum(), 0)

    def test_failed_reload_preserves_database_and_repeat_load_is_idempotent(self):
        with contextlib.redirect_stdout(io.StringIO()):
            load_data(self.raw, self.db)
        with contextlib.closing(connect_read_only(self.db)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM streaming").fetchone()[0], 96)
        before = self.db.read_bytes()
        invalid = self.tables["merchandise"].copy()
        invalid.loc[0, "revenue"] = -1
        invalid.to_csv(self.raw / "merchandise.csv", index=False)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
            load_data(self.raw, self.db)
        self.assertEqual(before, self.db.read_bytes())

    def test_content_filter_month_gaps_and_read_only_connection(self):
        with contextlib.closing(connect_read_only(self.db)) as connection:
            result = monthly_summary(connection, "2025-01", "2025-12", "C007")
            self.assertEqual(len(result), 12)
            self.assertEqual(result["participants"].sum(), 0)
            source = self.tables["streaming"]
            self.assertEqual(result["views"].sum(), source.loc[source.content_id.eq("C007"), "views"].sum())
            empty = monthly_summary(connection, "2026-01", "2026-02")
            self.assertEqual(empty["views"].tolist(), [0, 0])
            import sqlite3
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM contents")


if __name__ == "__main__":
    unittest.main()
