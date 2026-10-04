from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "entertainment.db"

# Keys describe the grain: what exactly does one row represent?
SCHEMAS = {
    "contents": {
        "columns": ["content_id", "title", "category", "release_date"],
        "key": ["content_id"],
        "numbers": [],
        "dates": {"release_date": "%Y-%m-%d"},
    },
    "streaming": {
        "columns": ["content_id", "month", "views", "watch_time"],
        "key": ["content_id", "month"],
        "numbers": ["views", "watch_time"],
        "dates": {"month": "%Y-%m"},
    },
    "merchandise": {
        "columns": ["content_id", "month", "sales_count", "revenue"],
        "key": ["content_id", "month"],
        "numbers": ["sales_count", "revenue"],
        "dates": {"month": "%Y-%m"},
    },
    "events": {
        "columns": ["content_id", "event_date", "participants", "ticket_revenue"],
        "key": ["content_id", "event_date"],
        "numbers": ["participants", "ticket_revenue"],
        "dates": {"event_date": "%Y-%m-%d"},
    },
}
