from datetime import datetime
from decimal import Decimal

from database import Tables, db


def create_event_ticket_charge(registration, created_by):
    """Create a user-owned ledger charge for a priced registration, never a membership."""
    price = Decimal(str(registration.price or 0))
    if price <= 0:
        return None
    manager = registration.RegisterManager
    event = Tables.Event.query.filter_by(id=manager.eventFK).first()
    name = f"{event.name} — {manager.name}" if event else (manager.name or "Eventticket")
    amount_cents = int((price * 100).quantize(Decimal("1")))
    charge = Tables.FinanceCharge(
        user_id=registration.userFK,
        registration_id=registration.id,
        kind="event_ticket",
        name_snapshot=name[:100],
        quantity=1,
        unit_price_cents=amount_cents,
        amount_cents=amount_cents,
        status="open",
        created_by=created_by,
    )
    db.session.add(charge)
    db.session.flush()
    from Sections.FinanceAllocations import allocate_existing_credit_to_charge

    allocate_existing_credit_to_charge(
        charge,
        changed_by=created_by,
        source="new_event_ticket",
        note="Vorhandenes Kontoguthaben wurde dem neuen Eventticket zugeordnet.",
    )
    return charge


def set_finance_charge_status(charge, status, changed_by, note=""):
    if charge.status == status:
        return False
    previous = charge.status
    charge.status = status
    charge.status_by = changed_by
    charge.status_at = datetime.now()
    charge.status_note = (note or "").strip()[:500] or None
    db.session.add(Tables.FinanceChargeStatusHistory(
        charge_id=charge.id,
        from_status=previous,
        to_status=status,
        changed_by=changed_by,
        changed_at=datetime.now(),
        note=charge.status_note,
    ))
    return True


def set_registration_paid(registration, paid, changed_by, source, note="", finance_status=None):
    """Update the scanner's canonical paid flag and append its audit record."""
    paid = bool(paid)
    previous = bool(registration.paid)
    charge = Tables.FinanceCharge.query.filter_by(registration_id=registration.id).first()
    if charge and not paid and source != "finance_allocation":
        from Sections.FinanceAllocations import release_charge_allocations

        release_charge_allocations(
            charge,
            changed_by,
            source="event_ticket_reopened",
            note=note or "Eventticket als unbezahlt markiert; Zahlungszuordnung freigegeben.",
        )
    desired_status = finance_status or ("paid" if paid else "open")
    charge_changed = set_finance_charge_status(charge, desired_status, changed_by, note) if charge else False
    if previous == paid and not charge_changed:
        return False
    registration.paid = paid
    if previous != paid:
        db.session.add(Tables.RegistrationPaymentHistory(
            registration_id=registration.id,
            from_paid=previous,
            to_paid=paid,
            changed_by=changed_by,
            changed_at=datetime.now(),
            source=source,
            note=(note or "").strip()[:500] or None,
        ))
    return True


def cancel_registration(registration, cancelled_by, reason):
    """Retain registration and ticket history while taking it out of active views."""
    if registration.cancelled_at:
        return False
    registration.cancelled_at = datetime.now()
    registration.cancelled_by = cancelled_by
    registration.cancel_reason = (reason or "").strip()[:500] or None
    charge = Tables.FinanceCharge.query.filter_by(registration_id=registration.id).first()
    if charge:
        from Sections.FinanceAllocations import release_charge_allocations

        release_charge_allocations(
            charge,
            cancelled_by,
            source="event_ticket_cancelled",
            note=registration.cancel_reason or "Storniertes Eventticket gibt die Zahlungszuordnung frei.",
        )
        set_finance_charge_status(charge, "cancelled", cancelled_by, registration.cancel_reason or "Storniert")
    return True
