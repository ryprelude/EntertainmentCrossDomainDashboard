"""Run after python -m src.load_data; Streamlit includes AppTest."""

import unittest

from streamlit.testing.v1 import AppTest

from src.settings import DB_PATH, ROOT


@unittest.skipUnless(DB_PATH.exists(), "Run python -m src.load_data before UI tests.")
class DashboardTests(unittest.TestCase):
    def test_default_view_and_content_without_events(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.tabs), 3)
        self.assertEqual(app.metric[3].value, "8")
        app.selectbox[0].select("C007").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[6].value, "0")
        app.selectbox[1].select("Event attendances").run()
        self.assertEqual(len(app.exception), 0)

    def test_period_filter_updates_all_views(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        full_year_views = app.metric[0].value
        app.select_slider[0].set_value(("2025-03", "2025-03")).run()
        self.assertEqual(len(app.exception), 0)
        self.assertNotEqual(app.metric[0].value, full_year_views)
        self.assertEqual(app.metric[3].value, "8")


if __name__ == "__main__":
    unittest.main()
