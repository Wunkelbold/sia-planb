import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "flask-server"))

from Sections.FinanceChargeState import allocation_charge_state, derived_charge_payment_state


def charge(*, amount_cents=1000, status="open", kind="drink", paid=False, legacy_paid_override=False):
    return SimpleNamespace(
        amount_cents=amount_cents,
        status=status,
        kind=kind,
        registration=SimpleNamespace(paid=paid) if kind == "event_ticket" else None,
        legacy_paid_override=legacy_paid_override,
    )


class FinanceAllocationStateTests(unittest.TestCase):
    def test_allocation_amount_derives_open_partial_and_paid_states(self):
        open_charge = charge()
        partial_charge = charge()
        paid_charge = charge()

        self.assertEqual("open", derived_charge_payment_state(open_charge, 0)["status"])
        partial_state = derived_charge_payment_state(partial_charge, 300)
        self.assertEqual("partially_paid", partial_state["status"])
        self.assertEqual(700, partial_state["remaining_cents"])
        self.assertEqual("paid", derived_charge_payment_state(paid_charge, 1000)["status"])

    def test_manual_event_ticket_paid_state_remains_canonical(self):
        event_charge = charge(kind="event_ticket", paid=True)

        state = derived_charge_payment_state(event_charge, 300)

        self.assertEqual("paid", state["status"])
        self.assertEqual(0, state["remaining_cents"])
        self.assertEqual(300, state["allocated_cents"])
        self.assertEqual("partially_paid", allocation_charge_state(event_charge, 300)["status"])

    def test_legacy_paid_override_is_preserved_without_allocations(self):
        legacy_charge = charge(legacy_paid_override=True)

        state = derived_charge_payment_state(legacy_charge, 0)

        self.assertEqual("paid", state["status"])
        self.assertEqual(0, state["remaining_cents"])

    def test_zero_value_and_cancelled_charges_have_terminal_states(self):
        waived_charge = charge(amount_cents=0)
        cancelled_charge = charge(status="cancelled")

        self.assertEqual("waived", derived_charge_payment_state(waived_charge, 0)["status"])
        self.assertEqual("cancelled", derived_charge_payment_state(cancelled_charge, 400)["status"])


if __name__ == "__main__":
    unittest.main()
