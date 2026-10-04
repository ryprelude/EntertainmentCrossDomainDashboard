"""Generate fictional, repeatable CSVs. Run: python -m src.generate_data"""

import argparse
import random
from pathlib import Path

import pandas as pd

from src.settings import RAW_DIR


def generate_data(output_dir=RAW_DIR, seed=42):
    rng = random.Random(seed)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # All names and commercial results are fictional.
    contents = pd.DataFrame([
        ["C001", "Starlight Sessions", "Music", "2023-05-12"],
        ["C002", "Pixel Odyssey", "Gaming", "2024-02-09"],
        ["C003", "Moonlit Letters", "Animation", "2024-04-18"],
        ["C004", "Neon Arcade", "Gaming", "2023-10-21"],
        ["C005", "Echoes of Tomorrow", "Music", "2024-08-03"],
        ["C006", "Cloud Garden", "Animation", "2024-06-14"],
        ["C007", "Afterglow Radio", "Music", "2024-11-01"],
        ["C008", "Pocket Quest", "Gaming", "2024-12-06"],
    ], columns=["content_id", "title", "category", "release_date"])

    # Separate popularity and merchandise demand: high views need not mean high sales.
    base_views = [220000, 280000, 140000, 180000, 120000, 95000, 85000, 70000]
    base_sales = [720, 380, 950, 560, 640, 820, 240, 310]
    growth = [0.045, 0.055, 0.030, 0.005, 0.070, 0.035, 0.020, 0.080]
    streaming, merchandise, events = [], [], []
    for index, content_id in enumerate(contents["content_id"]):
        for month in range(1, 13):
            period = f"2025-{month:02d}"
            trend = 1 + growth[index] * (month - 1)
            season = 1.18 if month in (7, 12) else 1.0
            views = round(base_views[index] * trend * season * rng.uniform(0.85, 1.15))
            hours = round(views * rng.uniform(5, 14) / 60)
            sales = round(base_sales[index] * trend * season * rng.uniform(0.80, 1.20))
            price = [2500, 3000, 3500, 2000][index % 4]
            streaming.append([content_id, period, views, hours])
            merchandise.append([content_id, period, sales, sales * price])

            # Two contents deliberately have no events, to exercise LEFT JOIN + zero fill.
            if index < 6 and month in (3, 6, 9, 12):
                participants = round((300 + index * 80) * trend * rng.uniform(0.8, 1.2))
                events.append([content_id, f"{period}-{10 + index:02d}",
                               participants, participants * 4500])

    tables = {
        "contents": contents,
        "streaming": pd.DataFrame(streaming, columns=["content_id", "month", "views", "watch_time"]),
        "merchandise": pd.DataFrame(merchandise, columns=["content_id", "month", "sales_count", "revenue"]),
        "events": pd.DataFrame(events, columns=["content_id", "event_date", "participants", "ticket_revenue"]),
    }
    for name, frame in tables.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8")
        print(f"[CREATED] {name}.csv: {len(frame)} rows")
    return tables


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate_data(args.output_dir, args.seed)
