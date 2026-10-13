def allocation_charge_state(charge, allocated_cents):
    if charge.status == "cancelled":
        return {"status": "cancelled", "allocated_cents": 0, "remaining_cents": 0}
    amount_cents = int(charge.amount_cents or 0)
    allocated_cents = int(allocated_cents)
    if amount_cents <= 0:
        return {"status": "waived", "allocated_cents": allocated_cents, "remaining_cents": 0}
    if allocated_cents >= amount_cents:
        status = "paid"
    elif allocated_cents > 0:
        status = "partially_paid"
    else:
        status = "open"
    return {
        "status": status,
        "allocated_cents": allocated_cents,
        "remaining_cents": max(0, amount_cents - allocated_cents),
    }


def derived_charge_payment_state(charge, allocated_cents):
    state = allocation_charge_state(charge, allocated_cents)
    if state["status"] == "cancelled":
        return state
    if charge.kind == "event_ticket" and charge.registration and charge.registration.paid:
        return {**state, "status": "paid", "remaining_cents": 0}
    if charge.legacy_paid_override and int(allocated_cents) == 0:
        return {**state, "status": "paid", "remaining_cents": 0}
    return state
