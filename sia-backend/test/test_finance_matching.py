import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "flask-server"))

from Sections.FinanceMatching import suggest_charge_match


def charge(uid, amount_cents, *, remaining_cents=None, status="open", due_date=None, created_at=None, kind="drink"):
    return SimpleNamespace(
        uid=uid,
        id=uid,
        amount_cents=amount_cents,
        remaining_cents=remaining_cents,
        status=status,
        due_date=due_date,
        created_at=created_at,
        kind=kind,
    )


class FinanceMatchingTests(unittest.TestCase):
    def test_suggests_every_open_charge_when_the_payment_covers_all(self):
        charges = [
            charge("newer", 300, created_at=datetime(2027, 2, 2)),
            charge("older", 500, created_at=datetime(2027, 2, 1)),
        ]

        result = suggest_charge_match(charges, 800)

        self.assertEqual(["older", "newer"], [item.uid for item in result["charges"]])
        self.assertEqual(800, result["total_cents"])
        self.assertEqual(0, result["remainder_cents"])
        self.assertTrue(result["all_open_charges"])

    def test_uses_a_combination_that_beats_a_greedy_first_charge(self):
        charges = [charge("six", 600), charge("five-a", 500), charge("five-b", 500)]

        result = suggest_charge_match(charges, 1000)

        self.assertEqual({"five-a", "five-b"}, {item.uid for item in result["charges"]})
        self.assertEqual(1000, result["total_cents"])

    def test_selects_the_largest_total_below_the_payment_when_there_is_no_exact_fit(self):
        charges = [charge("seven", 700), charge("six", 600), charge("four", 400)]

        result = suggest_charge_match(charges, 1050)

        self.assertEqual({"six", "four"}, {item.uid for item in result["charges"]})
        self.assertEqual(1000, result["total_cents"])
        self.assertEqual(50, result["remainder_cents"])

    def test_selects_all_charges_and_leaves_the_overpayment_unmatched(self):
        charges = [charge("dues", 1500, kind="membership"), charge("ticket", 800, kind="event_ticket")]

        result = suggest_charge_match(charges, 3000)

        self.assertEqual({"dues", "ticket"}, {item.uid for item in result["charges"]})
        self.assertEqual(2300, result["total_cents"])
        self.assertEqual(700, result["remainder_cents"])
        self.assertTrue(result["all_open_charges"])

    def test_returns_no_items_when_payment_is_smaller_than_every_open_charge(self):
        result = suggest_charge_match([charge("one-euro", 100)], 99)

        self.assertEqual([], result["charges"])
        self.assertEqual(0, result["total_cents"])
        self.assertFalse(result["all_open_charges"])

    def test_ignores_paid_cancelled_and_zero_value_charges(self):
        charges = [
            charge("paid", 200, status="paid"),
            charge("cancelled", 300, status="cancelled"),
            charge("zero", 0),
            charge("open", 100),
        ]

        result = suggest_charge_match(charges, 500)

        self.assertEqual(["open"], [item.uid for item in result["charges"]])
        self.assertTrue(result["all_open_charges"])

    def test_matches_only_the_remaining_part_of_a_partially_allocated_charge(self):
        charges = [
            charge("partially-paid", 2000, remaining_cents=700, status="partially_paid"),
            charge("other", 1000),
        ]

        result = suggest_charge_match(charges, 700)

        self.assertEqual(["partially-paid"], [item.uid for item in result["charges"]])
        self.assertEqual(700, result["total_cents"])

    def test_breaks_equal_total_ties_by_oldest_due_date(self):
        charges = [
            charge("later", 500, due_date=date(2027, 5, 1), created_at=datetime(2027, 1, 1)),
            charge("earlier", 500, due_date=date(2027, 4, 1), created_at=datetime(2027, 1, 2)),
        ]

        result = suggest_charge_match(charges, 500)

        self.assertEqual(["earlier"], [item.uid for item in result["charges"]])


if __name__ == "__main__":
    unittest.main()
