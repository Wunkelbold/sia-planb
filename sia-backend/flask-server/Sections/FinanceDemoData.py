"""Development-only member and ledger data for testing finance flows."""

from datetime import date, datetime, time, timedelta
import os

import click

from database import Tables, db
from globals import app, bcrypt


DEMO_MEMBERS = (
    {"username": "demowinter", "surname": "Demo", "lastname": "Winter", "category": "student", "since": "winter", "verification": "winter"},
    {"username": "demosummer", "surname": "Demo", "lastname": "Summer", "category": "student", "since": "summer", "verification": "current_and_next"},
    {"username": "demoprepay", "surname": "Demo", "lastname": "Prepay", "category": "student", "since": "january", "verification": "current_and_next"},
    {"username": "democontinue", "surname": "Demo", "lastname": "Continuing", "category": "student", "since": "old", "verification": "current_and_next"},
    {"username": "demoswitch", "surname": "Demo", "lastname": "Switch", "category": "student", "since": "old", "verification": "current_and_next"},
    {"username": "demofull", "surname": "Demo", "lastname": "Full", "category": "full", "since": "old"},
    {"username": "demodiscount", "surname": "Demo", "lastname": "Discount", "category": "full", "since": "old"},
    {"username": "demoreduced", "surname": "Demo", "lastname": "Reduced", "category": "reduced", "since": "old"},
    {"username": "demotraining", "surname": "Demo", "lastname": "Training", "category": "training", "since": "old"},
    {"username": "demoexempt", "surname": "Demo", "lastname": "Exempt", "category": "exempt", "since": "old"},
    {"username": "demospecial", "surname": "Demo", "lastname": "Special", "category": "special", "since": "old", "special_rate_cents": 3500},
    {"username": "demonewfull", "surname": "Demo", "lastname": "NewFull", "category": "full", "since": "new"},
)


def _demo_member_since(kind, year, today):
    if kind == "winter":
        return date(year, 10, 1)
    if kind == "summer":
        return date(year, 5, 15)
    if kind == "january":
        return date(year, 1, 15)
    if kind == "old":
        return date(year - 3, 1, 15)
    return today - timedelta(days=10)


def _make_demo_user(spec, password, role_name):
    username = spec["username"]
    user = Tables.User.query.filter_by(username=username).first()
    created_user = user is None
    if created_user:
        is_student = spec["category"] == "student"
        user = Tables.User(
            username=username,
            password=bcrypt.generate_password_hash(password).decode("utf-8"),
            surname=spec["surname"],
            lastname=spec["lastname"],
            email=f"{username}@demo.invalid",
            email_confirmed=True,
            hs_email=f"{username}@uni.invalid" if is_student else None,
            hs_email_confirmed=is_student,
            role=role_name,
            permissions=[],
            register_date=date.today().isoformat(),
            last_login="",
        )
        db.session.add(user)
        db.session.flush()

    membership = Tables.Membership.query.filter_by(user_id=user.id).first()
    if membership:
        return user, membership, False

    membership = Tables.Membership(
        user_id=user.id,
        status="active",
        fee_category=spec["category"],
        member_since=_demo_member_since(spec["since"], date.today().year, date.today()),
        special_rate_cents=spec.get("special_rate_cents"),
        created_by=None,
    )
    db.session.add(membership)
    db.session.flush()
    return user, membership, created_user


def _verified_cycle_years(spec, year):
    verification = spec.get("verification")
    if verification == "current":
        return [year]
    if verification == "winter":
        return [year + 1]
    if verification == "current_and_next":
        return [year, year + 1]
    return []


def _ensure_student_verifications(user, membership, spec, year, now):
    if membership.fee_category != "student" or not user.hs_email:
        return
    for cycle_year in _verified_cycle_years(spec, year):
        verification = Tables.MembershipStudentVerification.query.filter_by(
            membership_id=membership.id,
            cycle_year=cycle_year,
        ).first()
        if verification:
            continue
        db.session.add(Tables.MembershipStudentVerification(
            membership_id=membership.id,
            cycle_year=cycle_year,
            email_snapshot=user.hs_email.lower(),
            requested_at=now - timedelta(days=2),
            verified_at=now - timedelta(days=1),
        ))


def _get_or_create_run(cycle_year, period, created_by):
    run = Tables.FinanceBillingRun.query.filter_by(
        cycle_year=cycle_year,
        period=period,
        status="issued",
    ).first()
    if run:
        return run
    previous = Tables.FinanceBillingRun.query.filter_by(
        cycle_year=cycle_year,
    ).order_by(Tables.FinanceBillingRun.run_number.desc()).first()
    run = Tables.FinanceBillingRun(
        cycle_year=cycle_year,
        period=period,
        run_number=previous.run_number + 1 if previous else 1,
        status="issued",
        due_date=date(cycle_year, 3 if period == "march" else 9, 1),
        created_by=created_by,
    )
    db.session.add(run)
    db.session.flush()
    return run


def _seed_period_charges(memberships, run, period, cycle_year, created_by):
    from Sections.FinanceApi import create_membership_charge_record, dues_preview_for

    created = {}
    for username, membership in memberships.items():
        preview = dues_preview_for(membership, cycle_year, period)
        if (
            preview["already_billed"]
            or preview["not_eligible"]
            or preview["needs_admin_review"]
            or preview["amount_cents"] is None
        ):
            continue
        charge = create_membership_charge_record(
            membership,
            cycle_year,
            preview["amount_cents"],
            preview["effective_category"],
            date(cycle_year, 3 if period == "march" else 9, 1),
            created_by,
            f"Demo-Daten: {preview['reason']}",
            billing_run=run,
            period=period,
        )
        created[username] = charge
    return created


def _existing_run_charges(memberships, run, cycle_year):
    charges = {}
    for username, membership in memberships.items():
        charge = Tables.FinanceCharge.query.filter_by(
            membership_id=membership.id,
            billing_run_id=run.id,
            kind="membership",
            cycle_year=cycle_year,
        ).filter(
            Tables.FinanceCharge.status != "cancelled",
        ).order_by(Tables.FinanceCharge.id.desc()).first()
        if charge:
            charges[username] = charge
    return charges


def _add_payment(membership, amount_cents, reference, received_at, created_by, charge=None):
    from Sections.FinanceAllocations import allocate_unallocated_credit_to_charges

    payment = Tables.FinancePayment.query.filter_by(
        membership_id=membership.id,
        reference=reference,
    ).first()
    if not payment:
        payment = Tables.FinancePayment(
            membership_id=membership.id,
            user_id=membership.user_id,
            amount_cents=amount_cents,
            method="bank_transfer",
            reference=reference,
            note="Demo-Zahlung zum Testen der Beitrags- und Guthabenverrechnung.",
            received_at=received_at,
            recorded_by=created_by,
        )
        db.session.add(payment)
        db.session.flush()
    if charge:
        allocate_unallocated_credit_to_charges(
            membership.user_id,
            [charge],
            created_by,
            source="demo_seed",
            note="Demo-Daten: Zahlung einer Testbuchung zugeordnet.",
            require_full=False,
        )


@app.cli.command("seed-finance-demo")
@click.option("--year", type=int, default=None, help="Calendar year for March/September demo billing.")
@click.option("--password", default=None, help="Password shared by newly created demo accounts.")
def seed_finance_demo(year, password):
    """Seed development accounts for finance, proration, and payment-credit testing."""
    from Sections.FinanceApi import create_initial_membership_charge, reconcile_membership_year_charge

    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if app_env not in {"development", "dev", "test", "testing"}:
        raise click.ClickException("Demo finance data is only allowed when APP_ENV is development or test.")
    year = year or date.today().year
    if year < 2020 or year > date.today().year + 4:
        raise click.ClickException("Choose a calendar year from 2020 through four years ahead.")
    password = password or os.getenv("FINANCE_DEMO_PASSWORD") or "TestFinance2026!"
    role = Tables.Role.query.filter_by(name="Mitglied").first()
    if not role:
        raise click.ClickException("Role 'Mitglied' is missing. Start the app once so startup roles are initialized.")

    now = datetime.now()
    actor = Tables.User.query.filter_by(role="Admin").order_by(Tables.User.id.asc()).first()
    actor_id = actor.id if actor else None
    memberships = {}
    created_accounts = []
    try:
        for spec in DEMO_MEMBERS:
            user, membership, created = _make_demo_user(spec, password, role.name)
            if membership is None:
                continue
            memberships[spec["username"]] = membership
            _ensure_student_verifications(user, membership, spec, year, now)
            if created:
                created_accounts.append(spec["username"])

        db.session.flush()
        march_run = _get_or_create_run(year, "march", actor_id)
        march_charges = _seed_period_charges(memberships, march_run, "march", year, actor_id)
        for username, charge in _existing_run_charges(memberships, march_run, year).items():
            march_charges.setdefault(username, charge)

        switch = memberships.get("demoswitch")
        if switch and switch.fee_category == "student":
            switch_date = date(year, 7, 1)
            if switch_date >= date.today():
                switch_date = date.today() - timedelta(days=1)
            switch_category_history = Tables.MembershipHistory.query.filter_by(
                membership_id=switch.id,
                note="Demo-Daten: Wechsel von Student zu Vollbetrag im Sommersemester",
            ).first()
            if not switch_category_history:
                old_category = switch.fee_category
                switch.fee_category = "full"
                switch.updated_at = now
                db.session.add(Tables.MembershipHistory(
                    membership_id=switch.id,
                    changed_by=actor_id,
                    changed_at=datetime.combine(switch_date, time(12, 0)),
                    from_status="active",
                    to_status="active",
                    from_fee_category=old_category,
                    to_fee_category="full",
                    from_member_since=switch.member_since,
                    to_member_since=switch.member_since,
                    from_special_rate_cents=None,
                    to_special_rate_cents=None,
                    from_special_rate_valid_until=None,
                    to_special_rate_valid_until=None,
                    note="Demo-Daten: Wechsel von Student zu Vollbetrag im Sommersemester",
                ))
                db.session.flush()
                reconcile_membership_year_charge(
                    switch,
                    "membership_edit",
                    actor_id,
                    "Demo-Daten: Jahresbeitrag nach Kategorienwechsel aufgeteilt.",
                    cycle_year=year,
                )

        september_run = _get_or_create_run(year, "september", actor_id)
        september_charges = _seed_period_charges(memberships, september_run, "september", year, actor_id)
        for username, charge in _existing_run_charges(memberships, september_run, year).items():
            september_charges.setdefault(username, charge)

        prepay_charge = march_charges.get("demoprepay")
        _add_payment(
            memberships["demoprepay"],
            2000,
            f"DEMO-PREPAY-{year}",
            datetime(year, 3, 10, 12, 0),
            actor_id,
            prepay_charge,
        )
        _add_payment(
            memberships["demofull"],
            5000,
            f"DEMO-VOID-FULL-{year}",
            datetime(year, 3, 15, 12, 0),
            actor_id,
            march_charges.get("demofull"),
        )
        _add_payment(
            memberships["demosummer"],
            300,
            f"DEMO-SUMMER-PARTIAL-{year}",
            datetime(year, 9, 10, 12, 0),
            actor_id,
            september_charges.get("demosummer"),
        )
        # This payment intentionally remains unallocated until the next March run
        # creates the winter student's 9/12 charge.
        _add_payment(
            memberships["demowinter"],
            2000,
            f"DEMO-WINTER-PREPAY-{year}",
            now,
            actor_id,
        )

        for username, membership in memberships.items():
            if membership.fee_category != "student":
                continue
            for verification_year in (year, year + 1):
                verification = Tables.MembershipStudentVerification.query.filter_by(
                    membership_id=membership.id,
                    cycle_year=verification_year,
                ).first()
                if verification and verification.verified_at:
                    reconcile_membership_year_charge(
                        membership,
                        "student_verification",
                        actor_id,
                        "Demo-Daten: Studentennachweis für den Beitragszyklus bestätigt.",
                        cycle_year=verification_year,
                    )

        new_full = memberships.get("demonewfull")
        if new_full and new_full.member_since.year == date.today().year:
            create_initial_membership_charge(new_full, actor_id)
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        raise click.ClickException(f"Demo finance data was not created: {error}") from error

    click.echo(f"Created/reused March and September finance scenarios for {year}.")
    click.echo("Accounts: demowinter, demosummer, demoprepay, democontinue, demoswitch, demofull, demodiscount, demoreduced, demotraining, demoexempt, demospecial, demonewfull")
    if created_accounts:
        click.echo(f"New accounts: {', '.join(created_accounts)}")
        click.echo(f"Shared password for new accounts: {password}")
    else:
        click.echo("All demo accounts already existed; their passwords were not changed.")
    click.echo("Scenarios include 9/12 and 3/12 student fees, full annual categories, an open six-week new-member charge, partial payment, prepayment credit, payment-void testing, and a summer student-to-full category adjustment.")
