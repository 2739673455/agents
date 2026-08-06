from __future__ import annotations

import unittest
from datetime import date

from src.work_calendar import build_work_calendar


class WorkCalendarTest(unittest.TestCase):
    def test_holiday_periods_and_adjusted_workdays(self) -> None:
        calendar = build_work_calendar(date(2024, 1, 1), date(2026, 12, 31))

        self.assertEqual(calendar[date(2024, 9, 17)].holiday_name, "中秋节")
        self.assertEqual(calendar[date(2024, 9, 17)].is_workday, 0)
        self.assertEqual(calendar[date(2024, 9, 14)].is_workday, 1)
        self.assertEqual(calendar[date(2024, 9, 14)].is_holiday, 0)

        self.assertEqual(
            calendar[date(2025, 10, 6)].holiday_name,
            "中秋节",
        )
        self.assertEqual(calendar[date(2025, 10, 11)].is_workday, 1)

        self.assertEqual(calendar[date(2026, 2, 16)].holiday_name, "春节")
        self.assertEqual(calendar[date(2026, 2, 14)].is_workday, 1)
        self.assertEqual(calendar[date(2026, 6, 19)].holiday_name, "端午节")

    def test_unsupported_year_fails_instead_of_guessing(self) -> None:
        with self.assertRaisesRegex(ValueError, "2027"):
            build_work_calendar(date(2026, 1, 1), date(2027, 1, 1))


if __name__ == "__main__":
    unittest.main()
