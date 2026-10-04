"""Read-only SQL with aggregate-before-join to avoid multiplying fact rows."""

from contextlib import closing
import sqlite3

import pandas as pd

from src.settings import DB_PATH, SCHEMAS


CONTENT_SUMMARY_SQL = """
WITH streaming_totals AS (
    SELECT content_id, SUM(views) AS views, SUM(watch_time) AS watch_time
    FROM streaming WHERE month BETWEEN :start AND :end GROUP BY content_id
), merchandise_totals AS (
    SELECT content_id, SUM(sales_count) AS sales_count, SUM(revenue) AS revenue
    FROM merchandise WHERE month BETWEEN :start AND :end GROUP BY content_id
), event_totals AS (
    SELECT content_id, SUM(participants) AS participants, SUM(ticket_revenue) AS ticket_revenue
    FROM events WHERE substr(event_date, 1, 7) BETWEEN :start AND :end GROUP BY content_id
)
SELECT c.content_id, c.title, c.category,
       COALESCE(s.views, 0) AS views,
       COALESCE(s.watch_time, 0) AS watch_time,
       COALESCE(m.sales_count, 0) AS sales_count,
       COALESCE(m.revenue, 0) AS revenue,
       COALESCE(e.participants, 0) AS participants,
       COALESCE(e.ticket_revenue, 0) AS ticket_revenue
FROM contents c
LEFT JOIN streaming_totals s ON c.content_id = s.content_id
LEFT JOIN merchandise_totals m ON c.content_id = m.content_id
LEFT JOIN event_totals e ON c.content_id = e.content_id
ORDER BY revenue DESC, c.content_id
"""


def connect_read_only(db_path=DB_PATH):
    return sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)


def read_tables(connection):
    return {name: pd.read_sql_query(f"SELECT * FROM {name}", connection) for name in SCHEMAS}


def available_months(connection):
    rows = connection.execute("""
        SELECT month FROM streaming UNION SELECT month FROM merchandise
        UNION SELECT substr(event_date, 1, 7) FROM events ORDER BY 1
    """).fetchall()
    if not rows:
        return []
    return pd.period_range(rows[0][0], rows[-1][0], freq="M").astype(str).tolist()


def content_summary(connection, start, end):
    return pd.read_sql_query(CONTENT_SUMMARY_SQL, connection, params={"start": start, "end": end})


def monthly_summary(connection, start, end, content_id=None):
    # Each query returns one row per month before the data is combined.
    params = {"start": start, "end": end, "content_id": content_id}
    selection = "AND (:content_id IS NULL OR content_id = :content_id)"
    queries = {
        "views": f"SELECT month, SUM(views) AS views FROM streaming WHERE month BETWEEN :start AND :end {selection} GROUP BY month",
        "revenue": f"SELECT month, SUM(revenue) AS revenue FROM merchandise WHERE month BETWEEN :start AND :end {selection} GROUP BY month",
        "participants": f"SELECT substr(event_date, 1, 7) AS month, SUM(participants) AS participants FROM events WHERE substr(event_date, 1, 7) BETWEEN :start AND :end {selection} GROUP BY substr(event_date, 1, 7)",
    }
    calendar = pd.period_range(start, end, freq="M").astype(str)
    result = pd.DataFrame(index=calendar)
    result.index.name = "month"
    for column, query in queries.items():
        frame = pd.read_sql_query(query, connection, params=params).set_index("month")
        result[column] = frame[column].reindex(calendar, fill_value=0).astype("int64")
    return result.reset_index()


if __name__ == "__main__":
    if not DB_PATH.exists():
        raise SystemExit("Run python -m src.load_data first.")
    with closing(connect_read_only()) as connection:
        months = available_months(connection)
        if not months:
            raise SystemExit("No business data is available.")
        print(content_summary(connection, months[0], months[-1]).to_string(index=False))
