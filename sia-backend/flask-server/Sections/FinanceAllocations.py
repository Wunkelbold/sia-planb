from datetime import date, datetime

from sqlalchemy import or_

from database import Tables, db
from Sections.FinanceChargeState import (
    allocation_charge_state as _allocated_charge_state,
    derived_charge_payment_state,
)

_KEEP_DUE_DATE = object()


def user_membership_ids(user_id):
    return [row[0] for row in db.session.query(Tables.Membership.id).filter_by(user_id=user_id).all()]


def user_payments(user_id, active_only=True, for_update=False):
    membership_ids = user_membership_ids(user_id)
    clauses = [Tables.FinancePayment.user_id == user_id]
    if membership_ids:
        clauses.append(Tables.FinancePayment.membership_id.in_(membership_ids))
    query = Tables.FinancePayment.query.filter(or_(*clauses))
    if active_only:
        query = query.filter(Tables.FinancePayment.voided_at.is_(None))
    if for_update:
        query = query.with_for_update()
    return query.order_by(Tables.FinancePayment.received_at.asc(), Tables.FinancePayment.id.asc())


def allocation_amounts_for_charges(charge_ids):
    if not charge_ids:
        return {}
    rows = db.session.query(
        Tables.FinancePaymentAllocation.charge_id,
        db.func.coalesce(db.func.sum(Tables.FinancePaymentAllocation.amount_cents), 0),
    ).join(
        Tables.FinancePayment,
        Tables.FinancePayment.id == Tables.FinancePaymentAllocation.payment_id,
    ).filter(
        Tables.FinancePaymentAllocation.charge_id.in_(charge_ids),
        Tables.FinancePaymentAllocation.amount_cents > 0,
        Tables.FinancePayment.voided_at.is_(None),
    ).group_by(Tables.FinancePaymentAllocation.charge_id).all()
    return {charge_id: int(amount or 0) for charge_id, amount in rows}


def allocation_amounts_for_payments(payment_ids):
    if not payment_ids:
        return {}
    rows = db.session.query(
        Tables.FinancePaymentAllocation.payment_id,
        db.func.coalesce(db.func.sum(Tables.FinancePaymentAllocation.amount_cents), 0),
    ).join(
        Tables.FinancePayment,
        Tables.FinancePayment.id == Tables.FinancePaymentAllocation.payment_id,
    ).filter(
        Tables.FinancePaymentAllocation.payment_id.in_(payment_ids),
        Tables.FinancePaymentAllocation.amount_cents > 0,
        Tables.FinancePayment.voided_at.is_(None),
    ).group_by(Tables.FinancePaymentAllocation.payment_id).all()
    return {payment_id: int(amount or 0) for payment_id, amount in rows}


def allocated_cents_for_charge(charge):
    return allocation_amounts_for_charges([charge.id]).get(charge.id, 0)


def remaining_cents_for_charge(charge, allocated_cents=None):
    allocated_cents = allocated_cents_for_charge(charge) if allocated_cents is None else int(allocated_cents)
    return max(0, int(charge.amount_cents or 0) - allocated_cents)


def charge_payment_state(charge, allocated_cents=None):
    allocated_cents = allocated_cents_for_charge(charge) if allocated_cents is None else int(allocated_cents)
    return derived_charge_payment_state(charge, allocated_cents)


def _latest_registration_payment_history(registration_id):
    return Tables.RegistrationPaymentHistory.query.filter_by(
        registration_id=registration_id,
    ).order_by(
        Tables.RegistrationPaymentHistory.changed_at.desc(),
        Tables.RegistrationPaymentHistory.id.desc(),
    ).first()


def _write_charge_status(charge, status, changed_by, source, note):
    if charge.status == status:
        return False
    previous = charge.status
    changed_at = datetime.now()
    charge.status = status
    charge.status_by = changed_by
    charge.status_at = changed_at
    charge.status_note = (note or "").strip()[:500] or None
    db.session.add(Tables.FinanceChargeStatusHistory(
        charge_id=charge.id,
        from_status=previous,
        to_status=status,
        changed_by=changed_by,
        changed_at=changed_at,
        note=charge.status_note or f"Abgleichquelle: {source}",
    ))
    return True


def _payment_allocation_history(allocation, previous_amount, new_amount, changed_by, source, note):
    if previous_amount == new_amount:
        return
    db.session.add(Tables.FinancePaymentAllocationHistory(
        allocation_id=allocation.id,
        from_amount_cents=previous_amount,
        to_amount_cents=new_amount,
        changed_by=changed_by,
        changed_at=datetime.now(),
        source=source,
        note=(note or "").strip()[:1000] or None,
    ))


def unallocated_payment_cents(user_id):
    payments = user_payments(user_id).all()
    if not payments:
        return 0
    allocated = allocation_amounts_for_payments([payment.id for payment in payments])
    return sum(max(0, payment.amount_cents - allocated.get(payment.id, 0)) for payment in payments)


def allocated_cents_for_payment(payment):
    return allocation_amounts_for_payments([payment.id]).get(payment.id, 0)


def payment_allocation_rows(payment):
    rows = Tables.FinancePaymentAllocation.query.filter_by(payment_id=payment.id).order_by(
        Tables.FinancePaymentAllocation.id.asc(),
    ).all()
    result = []
    for allocation in rows:
        charge = Tables.FinanceCharge.query.filter_by(id=allocation.charge_id).first()
        if not charge:
            continue
        status = charge_payment_state(charge)
        history = Tables.FinancePaymentAllocationHistory.query.filter_by(
            allocation_id=allocation.id,
        ).order_by(
            Tables.FinancePaymentAllocationHistory.changed_at.asc(),
            Tables.FinancePaymentAllocationHistory.id.asc(),
        ).all()
        result.append({
            "charge_uid": str(charge.uid),
            "charge_name": charge.name_snapshot,
            "allocated_cents": allocation.amount_cents,
            "active_allocated_cents": 0 if payment.voided_at else allocation.amount_cents,
            "charge_remaining_cents": status["remaining_cents"],
            "released": allocation.amount_cents == 0 or bool(payment.voided_at),
            "history": [
                {
                    "from_amount_cents": event.from_amount_cents,
                    "to_amount_cents": event.to_amount_cents,
                    "source": event.source,
                    "note": event.note or "",
                    "changed_at": event.changed_at.isoformat(timespec="minutes"),
                }
                for event in history
            ],
        })
    return result


def _user_payment_records(user_id, for_update=False):
    membership_ids = [row[0] for row in db.session.query(Tables.Membership.id).filter_by(user_id=user_id).all()]
    filters = [Tables.FinancePayment.user_id == user_id]
    if membership_ids:
        filters.append(Tables.FinancePayment.membership_id.in_(membership_ids))
    query = Tables.FinancePayment.query.filter(or_(*filters)).filter(
        Tables.FinancePayment.voided_at.is_(None),
    ).order_by(Tables.FinancePayment.received_at.asc(), Tables.FinancePayment.id.asc())
    return query.with_for_update().all() if for_update else query.all()


def allocate_unallocated_credit_to_charges(user_id, charges, changed_by, source="payment_match", note="", require_full=True):
    charges = sorted(
        charges,
        key=lambda charge: (
            charge.due_date is None,
            charge.due_date or date.max,
            charge.created_at is None,
            charge.created_at or datetime.max,
            charge.id,
        ),
    )
    charge_amounts = allocation_amounts_for_charges([charge.id for charge in charges])
    remaining = {
        charge.id: max(0, int(charge.amount_cents or 0) - charge_amounts.get(charge.id, 0))
        for charge in charges
    }
    wanted = sum(remaining.values())
    payments = _user_payment_records(user_id, for_update=True)
    payment_amounts = allocation_amounts_for_payments([payment.id for payment in payments])
    available = sum(max(0, payment.amount_cents - payment_amounts.get(payment.id, 0)) for payment in payments)
    if require_full and wanted > available:
        raise ValueError("Das verfügbare, noch nicht zugeordnete Guthaben reicht für diese Buchungen nicht aus.")

    created_or_updated = []
    total_allocated = 0
    for charge in charges:
        charge_remaining = remaining[charge.id]
        if charge_remaining <= 0:
            continue
        for payment in payments:
            payment_remaining = max(0, payment.amount_cents - payment_amounts.get(payment.id, 0))
            if payment_remaining <= 0:
                continue
            amount = min(charge_remaining, payment_remaining)
            allocation = Tables.FinancePaymentAllocation.query.filter_by(
                payment_id=payment.id,
                charge_id=charge.id,
            ).with_for_update().first()
            if allocation:
                previous_amount = allocation.amount_cents
                allocation.amount_cents += amount
                allocation.updated_by = changed_by
                allocation.updated_at = datetime.now()
            else:
                allocation = Tables.FinancePaymentAllocation(
                    payment_id=payment.id,
                    charge_id=charge.id,
                    amount_cents=amount,
                    created_by=changed_by,
                    updated_by=changed_by,
                )
                db.session.add(allocation)
                db.session.flush()
                previous_amount = 0
            _payment_allocation_history(allocation, previous_amount, allocation.amount_cents, changed_by, source, note)
            created_or_updated.append(allocation)
            payment_amounts[payment.id] = payment_amounts.get(payment.id, 0) + amount
            charge_remaining -= amount
            total_allocated += amount
            if charge_remaining <= 0:
                break
        if charge_remaining > 0 and require_full:
            raise ValueError("Ein Teil der Buchungen konnte nicht vollständig zugeordnet werden.")

    for charge in charges:
        if charge.id in remaining and remaining[charge.id] > 0:
            charge.legacy_paid_override = False
            sync_charge_payment_state(charge, changed_by, source, note)
    return {"allocations": created_or_updated, "allocated_cents": total_allocated, "available_cents": available - total_allocated}


def allocate_existing_credit_to_charge(charge, changed_by=None, source="existing_credit", note="Guthaben wurde einer neuen Buchung zugeordnet."):
    user_id = charge.user_id
    if user_id is None and charge.membership_id:
        membership = Tables.Membership.query.filter_by(id=charge.membership_id).first()
        user_id = membership.user_id if membership else None
    if user_id is None or charge.status in {"cancelled", "waived"} or charge.legacy_paid_override:
        return 0
    result = allocate_unallocated_credit_to_charges(
        user_id,
        [charge],
        changed_by,
        source=source,
        note=note,
        require_full=False,
    )
    return result["allocated_cents"]


def release_charge_allocations(charge, changed_by=None, source="charge_cancelled", note="Zuordnung wegen stornierter Buchung freigegeben.", keep_cents=0):
    allocations = Tables.FinancePaymentAllocation.query.join(
        Tables.FinancePayment,
        Tables.FinancePayment.id == Tables.FinancePaymentAllocation.payment_id,
    ).filter(
        Tables.FinancePaymentAllocation.charge_id == charge.id,
        Tables.FinancePaymentAllocation.amount_cents > 0,
        Tables.FinancePayment.voided_at.is_(None),
    ).order_by(
        Tables.FinancePayment.received_at.desc(),
        Tables.FinancePayment.id.desc(),
        Tables.FinancePaymentAllocation.id.desc(),
    ).with_for_update().all()
    total = sum(allocation.amount_cents for allocation in allocations)
    excess = max(0, total - max(0, int(keep_cents)))
    released = 0
    for allocation in allocations:
        if excess <= 0:
            break
        amount = min(excess, allocation.amount_cents)
        previous_amount = allocation.amount_cents
        allocation.amount_cents -= amount
        allocation.updated_by = changed_by
        allocation.updated_at = datetime.now()
        _payment_allocation_history(allocation, previous_amount, allocation.amount_cents, changed_by, source, note)
        excess -= amount
        released += amount
    return released


def release_payment_allocations(payment, changed_by=None, source="payment_voided", note="Zuordnung wegen stornierter Zahlung freigegeben."):
    allocations = Tables.FinancePaymentAllocation.query.filter(
        Tables.FinancePaymentAllocation.payment_id == payment.id,
        Tables.FinancePaymentAllocation.amount_cents > 0,
    ).with_for_update().all()
    affected_charges = []
    for allocation in allocations:
        charge = Tables.FinanceCharge.query.filter_by(id=allocation.charge_id).with_for_update().first()
        if charge and charge not in affected_charges:
            affected_charges.append(charge)
        previous_amount = allocation.amount_cents
        allocation.amount_cents = 0
        allocation.updated_by = changed_by
        allocation.updated_at = datetime.now()
        _payment_allocation_history(allocation, previous_amount, 0, changed_by, source, note)
    return affected_charges


def sync_charge_payment_state(charge, changed_by=None, source="payment_allocation", note=""):
    state = charge_payment_state(charge)
    desired_status = state["status"]
    if charge.kind != "event_ticket" or not charge.registration:
        _write_charge_status(charge, desired_status, changed_by, source, note)
        return state

    registration = charge.registration
    allocation_state = _allocated_charge_state(charge, state["allocated_cents"])
    latest_history = _latest_registration_payment_history(registration.id) if registration.paid else None
    allocation_marked_ticket_paid = bool(
        latest_history
        and latest_history.source == "finance_allocation"
        and latest_history.to_paid
    )
    is_fully_allocated = charge.amount_cents > 0 and state["allocated_cents"] >= charge.amount_cents
    if is_fully_allocated and not registration.paid:
        from Sections.RegistrationService import set_registration_paid

        set_registration_paid(registration, True, changed_by, "finance_allocation", note, finance_status="paid")
    elif registration.paid and allocation_marked_ticket_paid and not is_fully_allocated:
        from Sections.RegistrationService import set_registration_paid

        set_registration_paid(
            registration,
            False,
            changed_by,
            "finance_allocation",
            note,
            finance_status=allocation_state["status"],
        )
    elif registration.paid:
        _write_charge_status(charge, "paid", changed_by, source, note)
    else:
        from Sections.RegistrationService import set_registration_paid

        set_registration_paid(registration, False, changed_by, "finance_allocation", note, finance_status=desired_status)
    return charge_payment_state(charge)


def reconcile_charge_amount(
    charge,
    new_amount_cents,
    new_fee_category,
    new_name,
    changed_by,
    source,
    note,
    new_due_date=_KEEP_DUE_DATE,
):
    new_amount_cents = max(0, int(new_amount_cents))
    previous_amount = charge.amount_cents
    previous_category = charge.fee_category_snapshot
    previous_name = charge.name_snapshot
    previous_due_date = charge.due_date
    updated_due_date = previous_due_date if new_due_date is _KEEP_DUE_DATE else new_due_date
    if (
        previous_amount == new_amount_cents
        and previous_category == new_fee_category
        and previous_name == new_name
        and previous_due_date == updated_due_date
    ):
        return False

    release_charge_allocations(
        charge,
        changed_by,
        source="charge_adjustment",
        note=f"Allocation reduced to fit revised charge: {note}",
        keep_cents=new_amount_cents,
    )
    charge.amount_cents = new_amount_cents
    charge.unit_price_cents = new_amount_cents
    charge.fee_category_snapshot = new_fee_category
    charge.name_snapshot = new_name[:100]
    charge.due_date = updated_due_date
    if new_amount_cents > previous_amount or new_amount_cents == 0:
        charge.legacy_paid_override = False
    db.session.add(Tables.FinanceChargeAdjustmentHistory(
        charge_id=charge.id,
        billing_run_id=charge.billing_run_id,
        cycle_year=charge.cycle_year,
        from_amount_cents=previous_amount,
        to_amount_cents=new_amount_cents,
        from_fee_category=previous_category,
        to_fee_category=new_fee_category,
        from_name=previous_name,
        to_name=new_name[:100],
        from_due_date=previous_due_date,
        to_due_date=updated_due_date,
        changed_by=changed_by,
        changed_at=datetime.now(),
        source=source,
        note=note[:1000] if note else None,
    ))
    sync_charge_payment_state(charge, changed_by, source, note)
    if new_amount_cents > previous_amount:
        allocate_existing_credit_to_charge(
            charge,
            changed_by=changed_by,
            source="charge_adjustment_credit",
            note="Vorhandenes Guthaben wurde auf den erhöhten Jahresbeitrag angerechnet.",
        )
    return True
