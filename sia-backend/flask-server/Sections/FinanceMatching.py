from datetime import date, datetime


def _charge_amount_cents(charge):
    remaining = getattr(charge, "match_remaining_cents", None)
    if remaining is None:
        remaining = getattr(charge, "remaining_cents", None)
    if remaining is None:
        remaining = getattr(charge, "amount_cents", 0)
    return int(remaining or 0)


def _charge_order(charge):
    due_date = getattr(charge, "due_date", None)
    created_at = getattr(charge, "created_at", None)
    return (
        due_date is None,
        due_date or date.max,
        created_at is None,
        created_at or datetime.max,
        getattr(charge, "id", 0) or 0,
    )


def suggest_charge_match(charges, payment_amount_cents):
    """Find the largest whole-charge total that does not exceed a payment."""
    payment_amount_cents = max(0, int(payment_amount_cents))
    candidates = sorted(
        (
            charge
            for charge in charges
            if getattr(charge, "match_status", getattr(charge, "status", None)) in {"open", "partially_paid"}
            and _charge_amount_cents(charge) > 0
        ),
        key=_charge_order,
    )
    open_total_cents = sum(_charge_amount_cents(charge) for charge in candidates)

    if not candidates or payment_amount_cents == 0:
        selected = []
    elif open_total_cents <= payment_amount_cents:
        selected = candidates
    else:
        reachable = {0}
        reachable_totals = [0]
        parents = {}
        for index, charge in enumerate(candidates):
            amount_cents = _charge_amount_cents(charge)
            if amount_cents > payment_amount_cents:
                continue
            previous_count = len(reachable_totals)
            for cursor in range(previous_count):
                previous_total = reachable_totals[cursor]
                total = previous_total + amount_cents
                if total <= payment_amount_cents and total not in reachable:
                    reachable.add(total)
                    reachable_totals.append(total)
                    parents[total] = (previous_total, index)

        total = max(reachable)
        selected_indices = set()
        while total:
            total, index = parents[total]
            selected_indices.add(index)
        selected = [
            charge for index, charge in enumerate(candidates)
            if index in selected_indices
        ]

    selected_total_cents = sum(_charge_amount_cents(charge) for charge in selected)
    return {
        "charges": selected,
        "total_cents": selected_total_cents,
        "payment_amount_cents": payment_amount_cents,
        "remainder_cents": payment_amount_cents - selected_total_cents,
        "all_open_charges": bool(candidates) and len(selected) == len(candidates),
    }
