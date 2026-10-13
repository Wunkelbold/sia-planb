import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "flask-server"))

from Sections.FinanceRules import (
    FEE_CATEGORY_LABELS,
    PDF_ANNUAL_RATE_DEFAULTS,
    calendar_year_amount_from_monthly_rates,
    next_student_billing_cycle_year,
    normalize_fee_category,
    prorated_annual_amount,
    student_billable_months,
    student_amount_for_period,
    student_first_billing_period,
)


class FinanceRulesTests(unittest.TestCase):
    def test_pdf_categories_and_legacy_alumni_mapping(self):
        self.assertEqual(5000, PDF_ANNUAL_RATE_DEFAULTS["full"])
        self.assertEqual(2500, PDF_ANNUAL_RATE_DEFAULTS["reduced"])
        self.assertEqual(2000, PDF_ANNUAL_RATE_DEFAULTS["student"])
        self.assertEqual(2000, PDF_ANNUAL_RATE_DEFAULTS["training"])
        self.assertEqual(0, PDF_ANNUAL_RATE_DEFAULTS["exempt"])
        self.assertEqual("full", normalize_fee_category("alumni"))
        self.assertEqual("Vollbetrag", FEE_CATEGORY_LABELS["alumni"])

    def test_student_first_invoice_is_prorated_by_the_join_semester(self):
        self.assertEqual((2026, "march", 9), student_first_billing_period(date(2026, 2, 28)))
        self.assertEqual((2026, "september", 3), student_first_billing_period(date(2026, 3, 1)))
        self.assertEqual((2026, "september", 3), student_first_billing_period(date(2026, 8, 31)))
        self.assertEqual((2027, "march", 9), student_first_billing_period(date(2026, 9, 1)))
        self.assertEqual((2027, "march", 9), student_first_billing_period(date(2026, 12, 31)))

    def test_student_run_amounts_do_not_duplicate_the_first_partial_year(self):
        summer_join = date(2026, 5, 12)
        winter_join = date(2026, 10, 12)
        self.assertEqual(500, student_amount_for_period(2000, summer_join, 2026, "september"))
        self.assertEqual(0, student_amount_for_period(2000, summer_join, 2026, "march"))
        self.assertEqual(2000, student_amount_for_period(2000, summer_join, 2027, "march"))
        self.assertEqual(1500, student_amount_for_period(2000, winter_join, 2027, "march"))
        self.assertEqual(0, student_amount_for_period(2000, winter_join, 2027, "september"))
        self.assertEqual(2000, student_amount_for_period(2000, winter_join, 2028, "march"))

    def test_student_membership_uses_only_post_semester_months_in_its_first_year(self):
        summer_join = date(2026, 5, 12)
        winter_join = date(2026, 10, 12)
        self.assertEqual(3, student_billable_months(summer_join, 2026))
        self.assertEqual(12, student_billable_months(summer_join, 2027))
        self.assertEqual(0, student_billable_months(winter_join, 2026))
        self.assertEqual(9, student_billable_months(winter_join, 2027))
        self.assertEqual(12, student_billable_months(winter_join, 2028))

    def test_year_amount_splits_rates_by_category_months(self):
        # Six months at the €20 student rate, then six months at €50 full rate.
        self.assertEqual(3500, calendar_year_amount_from_monthly_rates([2000] * 6 + [5000] * 6))

    def test_proration_rounds_cents_half_up(self):
        self.assertEqual(625, prorated_annual_amount(2500, 3))
        self.assertEqual(1875, prorated_annual_amount(2500, 9))

    def test_next_student_billing_period_tracks_march_and_september(self):
        self.assertEqual(2026, next_student_billing_cycle_year(date(2026, 2, 28)))
        self.assertEqual(2026, next_student_billing_cycle_year(date(2026, 7, 1)))
        self.assertEqual(2026, next_student_billing_cycle_year(date(2026, 9, 1)))
        self.assertEqual(2027, next_student_billing_cycle_year(date(2026, 10, 1)))


if __name__ == "__main__":
    unittest.main()
