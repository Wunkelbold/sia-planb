from datetime import date


PDF_ANNUAL_RATE_DEFAULTS = {
    "full": 5000,
    "reduced": 2500,
    "student": 2000,
    "training": 2000,
    "exempt": 0,
}

FEE_CATEGORY_LABELS = {
    "full": "Vollbetrag",
    "alumni": "Vollbetrag",
    "reduced": "Ermäßigt",
    "student": "Student:in",
    "training": "In Ausbildung",
    "exempt": "Befreit",
    "special": "Sonderbeitrag",
}


def normalize_fee_category(category):
    """Keep historical alumni rows readable while using the PDF's full-rate category."""
    return "full" if category == "alumni" else category


def student_first_billing_period(member_since):
    """Return the first student billing period after the joining semester ends.

    The March billing period covers April–December (9/12); the September
    period covers October–December (3/12). A March–August joiner reaches the
    September period in the same year. A September–February joiner reaches
    the March period in the same or following year.
    """
    if 3 <= member_since.month <= 8:
        return member_since.year, "september", 3
    cycle_year = member_since.year + 1 if member_since.month >= 9 else member_since.year
    return cycle_year, "march", 9


def prorated_annual_amount(annual_amount_cents, payable_months):
    """Return a half-up rounded monthly pro-rata of an annual amount."""
    return (int(annual_amount_cents) * int(payable_months) + 6) // 12


def student_first_payable_month(member_since, cycle_year):
    first_year, first_period, _ = student_first_billing_period(member_since)
    if cycle_year < first_year:
        return None
    if cycle_year > first_year:
        return 1
    return 4 if first_period == "march" else 10


def student_billable_months(member_since, cycle_year):
    first_month = student_first_payable_month(member_since, cycle_year)
    return 0 if first_month is None else 13 - first_month


def calendar_year_amount_from_monthly_rates(monthly_annual_amounts):
    """Sum annual-rate shares by calendar month and round once to cents."""
    return (sum(int(amount) for amount in monthly_annual_amounts) + 6) // 12


def student_amount_for_period(annual_amount_cents, member_since, cycle_year, period):
    first_year, first_period, first_period_months = student_first_billing_period(member_since)
    if cycle_year == first_year and period == first_period:
        return prorated_annual_amount(annual_amount_cents, first_period_months)
    if period == "march" and cycle_year > first_year:
        return int(annual_amount_cents)
    return 0


def next_student_billing_cycle_year(today=None):
    """Return the year for the next upcoming March/September student run."""
    today = today or date.today()
    if 3 <= today.month <= 9:
        return today.year
    return today.year + 1 if today.month >= 10 else today.year
