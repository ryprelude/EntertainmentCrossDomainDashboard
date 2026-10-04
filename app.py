"""Run from the project directory: python -m streamlit run app.py"""

from contextlib import closing
import sqlite3

import pandas as pd
import streamlit as st

from src.analysis import available_months, connect_read_only, content_summary, monthly_summary, read_tables
from src.settings import DB_PATH
from src.validate import passed, validate_tables


st.set_page_config(page_title="Entertainment | Cross-Domain Dashboard", page_icon="◈", layout="wide")


def show_metrics(views, revenue, participants, count=None):
    columns = st.columns(4 if count is not None else 3)
    columns[0].metric("Streaming views", f"{views:,}", border=True)
    columns[1].metric("Merchandise revenue · JPY", f"¥{revenue:,}", border=True)
    columns[2].metric("Event attendances", f"{participants:,}", border=True,
                      help="Sum of attendance counts, not unique people.")
    if count is not None:
        columns[3].metric("Contents in catalog", str(count), border=True,
                          help="All registered contents, including those without activity in the selected period.")


def main():
    if not DB_PATH.exists():
        st.title("Entertainment Cross-Domain Dashboard")
        st.info("Create the local database before opening the dashboard.")
        st.code("python -m src.generate_data\npython -m src.load_data", language="bash")
        st.stop()

    try:
        with closing(connect_read_only()) as connection:
            tables = read_tables(connection)
            report = validate_tables(tables)
            if not passed(report):
                st.error("The database did not pass validation. Fix the source CSVs and run python -m src.load_data.")
                st.dataframe(pd.DataFrame(report).query("status == 'FAIL'"), hide_index=True)
                st.stop()
            months = available_months(connection)
    except (sqlite3.Error, pd.errors.DatabaseError, ValueError) as error:
        st.error(f"Could not read the database: {error}")
        st.code("python -m src.load_data", language="bash")
        st.stop()
    if not months:
        st.info("The catalog is available, but no business activity has been loaded yet.")
        st.stop()

    with st.sidebar:
        st.markdown("### ◈ ENTERTAINMENT")
        st.caption("CROSS-DOMAIN DATA LAB")
        st.divider()
        st.markdown("**Reporting period**")
        if len(months) > 1:
            start, end = st.select_slider("Month range", options=months, value=(months[0], months[-1]))
        else:
            start = end = months[0]
            st.write(start)
        st.caption("The period applies to every KPI, chart and content detail.")
        st.divider()
        st.markdown("**Data coverage**")
        for label, name in (("Contents", "contents"), ("Streaming", "streaming"),
                            ("Merchandise", "merchandise"), ("Events", "events")):
            st.write(f"{label} · {len(tables[name]):,} rows")
        st.divider()
        st.caption("FICTIONAL DATA ONLY\n\nNo real company, customer or talent data is used.")

    with closing(connect_read_only()) as connection:
        summary = content_summary(connection, start, end)
        monthly = monthly_summary(connection, start, end)

    st.caption("ENTERTAINMENT INTELLIGENCE  /  PORTFOLIO DEMO")
    st.title("One catalog. Three perspectives.")
    st.write("Explore streaming, merchandise and live events through a shared content catalog.")
    st.caption(f"{start} — {end}  ·  All revenue in JPY  ·  Synthetic data")

    overview, detail, quality = st.tabs(["Company overview", "Content explorer", "Data quality"])
    with overview:
        show_metrics(int(summary.views.sum()), int(summary.revenue.sum()),
                     int(summary.participants.sum()), len(summary))
        st.write("")
        with st.container(border=True):
            st.subheader("Streaming momentum")
            st.caption("Monthly views across all contents")
            st.line_chart(monthly, x="month", y="views", x_label="Month", y_label="Views",
                          color="#5265E8", height=250)

        left, right = st.columns([1, 1.2])
        with left, st.container(border=True):
            st.subheader("Merchandise by content")
            st.caption("Revenue during the selected period · JPY")
            chart = summary.rename(columns={"title": "Content", "revenue": "Revenue (JPY)"})
            st.bar_chart(chart, x="Content", y="Revenue (JPY)", horizontal=True,
                         sort="-Revenue (JPY)", color="#5265E8", height=310)
        with right, st.container(border=True):
            st.subheader("Reach & merchandise")
            st.caption("One point per content · match IDs with the totals below")
            chart = summary.rename(columns={"content_id": "Content ID", "views": "Views", "revenue": "Revenue (JPY)"})
            st.scatter_chart(chart, x="Views", y="Revenue (JPY)", color="Content ID", size=170, height=310)
        st.caption("Views and revenue have different units. This comparison describes patterns in mock data; it does not establish causation.")
        with st.expander("View cross-domain totals"):
            st.dataframe(summary, hide_index=True)

    with detail:
        st.subheader("Follow a single content")
        catalog = tables["contents"].set_index("content_id")
        content_id = st.selectbox("Content", catalog.index.tolist(),
                                  format_func=lambda key: f"{catalog.loc[key, 'title']} · {key}")
        row = summary.loc[summary.content_id.eq(content_id)].iloc[0]
        st.caption(f"{row.category}  ·  Released {catalog.loc[content_id, 'release_date']}  ·  {start} — {end}")
        show_metrics(int(row.views), int(row.revenue), int(row.participants))
        with closing(connect_read_only()) as connection:
            trend = monthly_summary(connection, start, end, content_id)
        metric = st.selectbox("Monthly metric", ["Streaming views", "Merchandise revenue (JPY)", "Event attendances"])
        metric_column = {"Streaming views": "views", "Merchandise revenue (JPY)": "revenue", "Event attendances": "participants"}[metric]
        with st.container(border=True):
            st.line_chart(trend, x="month", y=metric_column, x_label="Month", y_label=metric,
                          color="#5265E8", height=320)
        st.caption("Months with no recorded activity are displayed as 0. Metrics are shown separately to preserve their units.")
        st.dataframe(trend, hide_index=True)

    with quality:
        st.subheader("Reliable inputs, explainable outputs")
        st.success(f"{len(report)} / {len(report)} validation checks passed on the loaded database.")
        st.write("Required values, duplicate rows and keys, numeric ranges, date formats and content references are checked before loading.")
        st.caption("This panel checks the current database snapshot. CSV edits appear only after you run python -m src.load_data again.")
        st.dataframe(pd.DataFrame(report), hide_index=True, height=330)
        st.markdown("**How the domains connect**")
        st.write("Each domain is aggregated by content_id first. The results are then LEFT JOINed to the catalog, keeping contents with no events and avoiding duplicated totals.")
        st.caption("Mock-data convention: missing fact rows mean no recorded activity. Production systems must distinguish zero activity from missing ingestion.")

    st.divider()
    st.caption("Collect → Validate → Store → Integrate → Analyze → Visualize  ·  Python / Pandas / SQLite / Streamlit")


if __name__ == "__main__":
    main()
