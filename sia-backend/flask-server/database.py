import os
import sys
import traceback
from flask import json
import psycopg2
from psycopg2 import OperationalError, DatabaseError, InterfaceError
from flask_login import UserMixin
import logging
from globals import *
import uuid
import secrets
from sqlalchemy.dialects.postgresql import UUID, MONEY
from sqlalchemy import text
from datetime import datetime, timezone


def format_datetime(dt):
    return dt.strftime('%d-%m-%Y %H:%M') if dt else None

def format_datetime_hr(dt):
    local_tz = ZoneInfo("Europe/Berlin")
    locale.setlocale(locale.LC_ALL, 'de_DE.utf8')
    return dt.replace(tzinfo=local_tz).strftime('%a, %d.%m.%y %H:%M') if dt else None

def format_datetime2(dt):
    return dt.strftime('%Y-%m-%dT%H:%M') if dt else None

class Tables:
    class User(db.Model, UserMixin):
        __tablename__ = 'user'
        id = db.Column(db.Integer, primary_key=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)  # Add UUID
        username = db.Column(db.String(20), nullable=False, unique=True)
        surname = db.Column(db.String(20))
        lastname = db.Column(db.String(20))
        street = db.Column(db.String(25))
        street_no = db.Column(db.String(10))
        password = db.Column(db.String(200))
        email = db.Column(db.String(30))
        email_confirmed = db.Column(db.Boolean, nullable=False, default=False)
        email_confirm_token = db.Column(db.String(64))
        email_cooldown = db.Column(db.TEXT, default=datetime.min)
        hs_email = db.Column(db.String(30))
        hs_email_confirmed = db.Column(db.Boolean, nullable=False, default=False)
        hs_email_confirm_token = db.Column(db.String(64))
        hs_email_cooldown = db.Column(db.TEXT,default=datetime.min)
        city = db.Column(db.String(25))
        postalcode = db.Column(db.String(25))
        register_date = db.Column(db.TEXT)
        last_login = db.Column(db.TEXT)
        role = db.Column(db.TEXT, db.ForeignKey("roles.name"), nullable=False)
        permissions = db.Column(db.ARRAY(db.TEXT), nullable=False)
        calendar_url = db.Column(db.String(64), unique=True)  # Random ID for personal calendar
        last_updated = db.Column(db.TEXT)

    class Role(db.Model):
        __tablename__ = 'roles'
        name = db.Column(db.TEXT, primary_key=True)
        permissions = db.Column(db.ARRAY(db.TEXT), nullable=False)
        selectable_on_register = db.Column(db.String(10))
        requestable_on_change = db.Column(db.Boolean, nullable=False, default=False)
        
    class Event(db.Model):
        __tablename__ = 'events'
        id = db.Column(db.Integer, primary_key=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)  # Add UUID
        author = db.Column(db.Integer, db.ForeignKey("user.id",ondelete='SET DEFAULT'), nullable=False, default=1)
        name = db.Column(db.String(50), nullable=False)
        visibility = db.Column(db.String(10))
        place = db.Column(db.String(50))
        created = db.Column(db.DateTime)
        date = db.Column(db.DateTime)
        end = db.Column(db.DateTime)
        description = db.Column(db.String(2000))
        postername = db.Column(db.String(50))
        shift_rel = db.relationship("Shift", cascade="all,delete", backref="Event", lazy="joined")
        task_rel = db.relationship("Task", cascade="all,delete", backref="Event", lazy="joined")

        def toJSON(self):
            def format_datetime(dt):
                return dt.strftime('%Y-%m-%dT%H:%M') if dt else None
            return json.dumps({
                "id": self.id,
                "author": self.author,
                "uid": self.uid,
                "name": self.name,
                "visibility": self.visibility,
                "place": self.place,
                "created": format_datetime(self.created),
                "date": format_datetime(self.date),
                "description": self.description,
                "postername": self.postername
            })
    
    class Shift(db.Model):
        __tablename__ = 'shifts'
        id = db.Column(db.Integer, primary_key=True)
        event = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
        type = db.Column(db.String(30))
        start = db.Column(db.DateTime)
        end = db.Column(db.DateTime)
        duty_rel = db.relationship("Duty", cascade="all,delete", backref="Shift", lazy="joined")
        
        def getDict(self):
            return {
                "id": self.id,
                "event": self.event,
                "type": self.type,
                "start": format_datetime(self.start),
                "end": format_datetime(self.end),
                "start_hr": format_datetime_hr(self.start),
                "end_hr": format_datetime_hr(self.end),
                "users": [duty.user_obj.username for duty in self.duty_rel if duty.user_obj]
            }
        
    class Duty(db.Model):
        __tablename__ = 'duty'
        id = db.Column(db.Integer, primary_key=True)
        shift = db.Column(db.Integer, db.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False)
        user = db.Column(db.Integer, db.ForeignKey("user.id",ondelete="CASCADE"))
        joined_timestamp = db.Column(db.DateTime)
        assigned_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        user_obj = db.relationship("User", foreign_keys=[user], backref="duties", lazy="joined")

    class Contact(db.Model):
        __tablename__ = 'contact'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)  # Add UUID
        category = db.Column(db.String(20))
        surname = db.Column(db.String(20))
        lastname = db.Column(db.String(20))
        email = db.Column(db.String(30))
        message = db.Column(db.String(500))
        created = db.Column(db.TEXT)
        creation = db.Column(db.DateTime)
        handled_at = db.Column(db.DateTime)
        handled_by = db.Column(db.Integer, db.ForeignKey("user.id", name="contact_handled_by_fkey", ondelete="SET NULL"))
        handled_by_obj = db.relationship("User", foreign_keys=[handled_by])
        
        def getDict(self):
            return {
                "id":self.id,
                "uid":self.uid,
                "category": self.category,
                "surname":self.surname,
                "lastname":self.lastname,
                "email":self.email,
                "message":self.message,
                "creation":format_datetime_hr(self.creation),
                "handled_at":format_datetime_hr(self.handled_at) if self.handled_at else None,
                "handled_by_username": self.handled_by_obj.username if self.handled_by_obj else None,
                "is_handled": self.handled_at is not None,
            }

    class RegisterManager(db.Model):
        __tablename__ = 'registermanager'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        name = db.Column(db.String(30))
        visibility = db.Column(db.String(10))
        accept = db.Column(db.String(12))
        deny = db.Column(db.String(12))
        start = db.Column(db.DateTime)
        end = db.Column(db.DateTime)
        price = db.Column(Numeric(10, 2))
        eventFK = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"))
        registration_rel = db.relationship("Registration", cascade="all,delete", backref="RegisterManager", lazy="joined")


        def getDict(self):
            return {
                "rmID": self.id,
                "name": self.name,
                "visibility": self.visibility,
                "accept": self.accept,
                "deny":self.deny,
                "start": format_datetime2(self.start),
                "end": format_datetime2(self.end),
                "start_hr": format_datetime_hr(self.start),
                "end_hr": format_datetime_hr(self.end),
                "price": self.price,
                "eventFK": self.eventFK,
                "users": [
                            registration.user_obj.username
                            for registration in sorted(
                                self.registration_rel,
                                key=lambda registration: registration.timestamp.isoformat() if registration.timestamp else "",
                            ) if registration.user_obj and not registration.cancelled_at
                        ]
            }

    class Registration(db.Model):
        __tablename__ = 'registration'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        timestamp = db.Column(db.DateTime)
        userFK = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
        rmFK = db.Column(db.Integer, db.ForeignKey("registermanager.id", ondelete="CASCADE"))
        teamname = db.Column(db.String(30))
        price = db.Column(Numeric(10, 2))
        paid = db.Column(db.Boolean, default=False)
        valid = db.Column(db.Boolean, default=False) # Ticket eingeloest / entwertet
        created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        cancelled_at = db.Column(db.DateTime)
        cancelled_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        cancel_reason = db.Column(db.Text)
        __table_args__ = (db.Index("ix_registration_active_user_option", "userFK", "rmFK", "cancelled_at"),)
        user_obj = db.relationship("User", foreign_keys=[userFK], backref="registration", lazy="joined")

        def getDict(self):
            return {
                "id": self.id,
                "userFK": self.userFK,
                "userUID": self.user_obj.uid,
                "rmFK": self.rmFK,
                "teamname": self.teamname,
                "users": self.user_obj.username,
                "rm_name": self.RegisterManager.name,
                "price" : self.price,
                "paid": self.paid,
                "valid": self.valid, 
                "cancelled_at": format_datetime(self.cancelled_at) if self.cancelled_at else None,
            }

    class RegistrationPaymentHistory(db.Model):
        __tablename__ = "registration_payment_history"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        registration_id = db.Column(db.Integer, db.ForeignKey("registration.id", ondelete="CASCADE"), nullable=False)
        from_paid = db.Column(db.Boolean, nullable=False)
        to_paid = db.Column(db.Boolean, nullable=False)
        changed_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        changed_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        source = db.Column(db.String(20), nullable=False)
        note = db.Column(db.Text)
        __table_args__ = (db.Index("ix_registration_payment_history", "registration_id", "changed_at"),)
        
    class Task(db.Model):
        __tablename__ = 'task'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        eventFK = db.Column(db.Integer, db.ForeignKey("events.id",ondelete="CASCADE"))
        authorFK = db.Column(db.Integer, db.ForeignKey("user.id",ondelete='SET DEFAULT'),default=1)
        name = db.Column(db.String(50))
        description = db.Column(db.String(500))
        status = db.Column(db.String(30))
        priority = db.Column(db.String(20))
        visibility = db.Column(db.String(10))
        deadline = db.Column(db.DateTime)
        created = db.Column(db.DateTime)
        timeframe_start = db.Column(db.DateTime)
        timeframe_end = db.Column(db.DateTime) 
        assistant_obj = db.relationship("Assistant", backref="task", lazy="joined")

        def getDict(self):
            return {
                "id": self.id,
                "eventFK": self.eventFK,
                "name": self.name,
                "authorFK": self.authorFK,
                "description": self.description,
                "status": self.status,
                "priority": self.priority,
                "visibility": self.visibility,
                "deadline" : format_datetime2(self.deadline),
                "deadline_hr" : format_datetime_hr(self.deadline),
                "created": format_datetime_hr(self.created),
                "timeframe_start": format_datetime2(self.timeframe_start),
                "timeframe_end": format_datetime2(self.timeframe_end),
                "timeframe_start_hr": format_datetime_hr(self.timeframe_start),
                "timeframe_end_hr": format_datetime_hr(self.timeframe_end),
                "event_name": self.Event.name if self.Event else " - ",
                "eventFK": self.Event.id if self.Event else " - ",
            }

    class Assistant(db.Model): #Helfer die Aufgaben erledigen
        __tablename__ = 'assistant'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        userFK = db.Column(db.Integer, db.ForeignKey("user.id",ondelete="CASCADE"))
        taskFK = db.Column(db.Integer, db.ForeignKey("task.id",ondelete="CASCADE"))
        joined_timestamp = db.Column(db.DateTime)
        assigned_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        role = db.Column(db.String(30))
        user_obj = db.relationship("User", foreign_keys=[userFK], backref="assistant_assignments", lazy="joined")

    class Membership(db.Model):
        __tablename__ = "membership"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), unique=True, nullable=False)
        status = db.Column(db.String(20), nullable=False, default="active")
        fee_category = db.Column(db.String(20), nullable=False, default="student")
        member_since = db.Column(db.Date, nullable=False)
        ended_at = db.Column(db.Date)
        special_rate_cents = db.Column(db.Integer)
        special_rate_valid_until = db.Column(db.Date)
        created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        __table_args__ = (
            db.CheckConstraint(
                "fee_category IN ('full', 'reduced', 'student', 'training', 'exempt', 'special')",
                name="membership_category_valid",
            ),
            db.Index("ix_membership_status", "status"),
        )
        user_obj = db.relationship("User", foreign_keys=[user_id], backref=db.backref("membership", uselist=False))

    class MembershipHistory(db.Model):
        __tablename__ = "membership_history"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        membership_id = db.Column(db.Integer, db.ForeignKey("membership.id", ondelete="RESTRICT"), nullable=False)
        changed_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        changed_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        from_status = db.Column(db.String(20))
        to_status = db.Column(db.String(20))
        from_fee_category = db.Column(db.String(20))
        to_fee_category = db.Column(db.String(20))
        from_member_since = db.Column(db.Date)
        to_member_since = db.Column(db.Date)
        from_special_rate_cents = db.Column(db.Integer)
        to_special_rate_cents = db.Column(db.Integer)
        from_special_rate_valid_until = db.Column(db.Date)
        to_special_rate_valid_until = db.Column(db.Date)
        note = db.Column(db.Text)
        __table_args__ = (db.Index("ix_membership_history_member_changed", "membership_id", "changed_at"),)

    class MembershipFeeRate(db.Model):
        __tablename__ = "membership_fee_rate"
        category = db.Column(db.String(20), primary_key=True)
        annual_amount_cents = db.Column(db.Integer, nullable=False)
        updated_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        __table_args__ = (
            db.CheckConstraint(
                "category IN ('full', 'reduced', 'student', 'training', 'exempt')",
                name="membership_fee_rate_category_valid",
            ),
            db.CheckConstraint("annual_amount_cents >= 0", name="membership_fee_rate_amount_nonnegative"),
        )

    class MembershipRequest(db.Model):
        __tablename__ = "membership_request"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
        request_type = db.Column(db.String(20), nullable=False, default="category")
        requested_category = db.Column(db.String(20), nullable=False)
        request_note = db.Column(db.Text)
        status = db.Column(db.String(20), nullable=False, default="pending")
        submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        reviewed_at = db.Column(db.DateTime)
        review_note = db.Column(db.Text)
        __table_args__ = (
            db.CheckConstraint(
                "requested_category IN ('full', 'reduced', 'student', 'training', 'exempt', 'special')",
                name="membership_request_category_valid",
            ),
            db.Index("ix_membership_request_status", "status", "submitted_at"),
        )

    class UserRoleRequest(db.Model):
        __tablename__ = "user_role_request"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
        from_role = db.Column(db.Text, db.ForeignKey("roles.name", ondelete="RESTRICT"), nullable=False)
        requested_role = db.Column(db.Text, db.ForeignKey("roles.name", ondelete="RESTRICT"), nullable=False)
        request_note = db.Column(db.Text, nullable=False)
        status = db.Column(db.String(20), nullable=False, default="pending")
        submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        reviewed_at = db.Column(db.DateTime)
        review_note = db.Column(db.Text)
        user_obj = db.relationship("User", foreign_keys=[user_id])
        __table_args__ = (
            db.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'withdrawn')", name="user_role_request_status_valid"),
            db.CheckConstraint("from_role <> requested_role", name="user_role_request_distinct_roles"),
            db.Index("ix_user_role_request_status", "status", "submitted_at"),
            db.Index(
                "uq_user_role_request_pending",
                "user_id",
                unique=True,
                postgresql_where=text("status = 'pending'"),
            ),
        )

    class MembershipStudentVerification(db.Model):
        __tablename__ = "membership_student_verification"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        membership_id = db.Column(db.Integer, db.ForeignKey("membership.id", ondelete="RESTRICT"), nullable=False)
        cycle_year = db.Column(db.Integer, nullable=False)
        email_snapshot = db.Column(db.String(255), nullable=False)
        requested_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        verified_at = db.Column(db.DateTime)
        __table_args__ = (db.UniqueConstraint("membership_id", "cycle_year", name="membership_student_verification_cycle_key"),)

    class TallyItem(db.Model):
        __tablename__ = "tally_item"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
        name = db.Column(db.String(80), nullable=False, unique=True)
        price_cents = db.Column(db.Integer)
        is_active = db.Column(db.Boolean, nullable=False, default=False)
        created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        updated_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    class DrinkMenuSection(db.Model):
        __tablename__ = "drink_menu_section"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
        title = db.Column(db.String(80), nullable=False)
        subtitle = db.Column(db.String(200))
        price_cents = db.Column(db.Integer)
        show_price = db.Column(db.Boolean, nullable=False, default=False)
        sort_order = db.Column(db.Integer, nullable=False, default=0)
        is_active = db.Column(db.Boolean, nullable=False, default=True)
        created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        updated_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        __table_args__ = (
            db.CheckConstraint("price_cents IS NULL OR price_cents >= 0", name="drink_menu_section_price_nonnegative"),
            db.Index("ix_drink_menu_section_active_order", "is_active", "sort_order"),
        )

    class DrinkMenuItem(db.Model):
        __tablename__ = "drink_menu_item"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
        section_id = db.Column(db.Integer, db.ForeignKey("drink_menu_section.id", ondelete="CASCADE"), nullable=False)
        group_label = db.Column(db.String(80))
        name = db.Column(db.String(80), nullable=False)
        description = db.Column(db.String(200))
        volume_label = db.Column(db.String(40))
        price_cents = db.Column(db.Integer)
        show_price = db.Column(db.Boolean, nullable=False, default=True)
        image_path = db.Column(db.String(255))
        sort_order = db.Column(db.Integer, nullable=False, default=0)
        is_active = db.Column(db.Boolean, nullable=False, default=True)
        created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        updated_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        __table_args__ = (
            db.CheckConstraint("price_cents IS NULL OR price_cents >= 0", name="drink_menu_item_price_nonnegative"),
            db.Index("ix_drink_menu_item_section_order", "section_id", "sort_order"),
        )

    class FinanceBillingRun(db.Model):
        __tablename__ = "finance_billing_run"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        cycle_year = db.Column(db.Integer, nullable=False)
        period = db.Column(db.String(12), nullable=False, default="march")
        run_number = db.Column(db.Integer, nullable=False, default=1)
        status = db.Column(db.String(20), nullable=False, default="issued")
        due_date = db.Column(db.Date, nullable=False)
        created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        voided_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        voided_at = db.Column(db.DateTime)
        void_reason = db.Column(db.Text)
        __table_args__ = (
            db.CheckConstraint("run_number > 0", name="finance_billing_run_number_positive"),
            db.CheckConstraint("status IN ('issued', 'voided')", name="finance_billing_run_status_valid"),
            db.CheckConstraint("period IN ('march', 'september')", name="finance_billing_run_period_valid"),
            db.UniqueConstraint("cycle_year", "run_number", name="finance_billing_run_cycle_run_key"),
            db.Index(
                "ix_finance_billing_run_one_issued_period",
                "cycle_year",
                "period",
                unique=True,
                postgresql_where=text("status = 'issued'"),
            ),
        )

    class FinanceCharge(db.Model):
        __tablename__ = "finance_charge"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
        membership_id = db.Column(db.Integer, db.ForeignKey("membership.id", ondelete="RESTRICT"))
        user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
        registration_id = db.Column(db.Integer, db.ForeignKey("registration.id", ondelete="RESTRICT"))
        billing_run_id = db.Column(db.Integer, db.ForeignKey("finance_billing_run.id", ondelete="SET NULL"))
        tally_item_id = db.Column(db.Integer, db.ForeignKey("tally_item.id", ondelete="SET NULL"))
        kind = db.Column(db.String(20), nullable=False)
        name_snapshot = db.Column(db.String(100), nullable=False)
        fee_category_snapshot = db.Column(db.String(20))
        cycle_year = db.Column(db.Integer)
        quantity = db.Column(db.Integer, nullable=False, default=1)
        unit_price_cents = db.Column(db.Integer, nullable=False, default=0)
        amount_cents = db.Column(db.Integer, nullable=False)
        due_date = db.Column(db.Date)
        status = db.Column(db.String(20), nullable=False, default="open")
        created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        status_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        status_at = db.Column(db.DateTime)
        status_note = db.Column(db.Text)
        legacy_paid_override = db.Column(db.Boolean, nullable=False, default=False)
        __table_args__ = (
            db.CheckConstraint("kind IN ('drink', 'membership', 'event_ticket')", name="finance_charge_kind_valid"),
            db.CheckConstraint("status IN ('open', 'partially_paid', 'paid', 'cancelled', 'waived')", name="finance_charge_status_valid"),
            db.CheckConstraint("membership_id IS NOT NULL OR user_id IS NOT NULL", name="finance_charge_owner_required"),
            db.CheckConstraint(
                "kind <> 'event_ticket' OR (user_id IS NOT NULL AND registration_id IS NOT NULL)",
                name="finance_charge_event_ticket_registration_required",
            ),
            db.CheckConstraint("amount_cents >= 0", name="finance_charge_amount_nonnegative"),
            db.CheckConstraint("quantity > 0", name="finance_charge_quantity_positive"),
            db.UniqueConstraint("registration_id", name="finance_charge_registration_key"),
            db.UniqueConstraint("membership_id", "kind", "cycle_year", "billing_run_id", name="finance_charge_membership_run_key"),
            db.Index("ix_finance_charge_user_status", "user_id", "status", "created_at"),
            db.Index("ix_finance_charge_member_status", "membership_id", "status", "created_at"),
            db.Index("ix_finance_charge_billing_run", "billing_run_id"),
        )
        registration = db.relationship("Registration", foreign_keys=[registration_id], backref=db.backref("finance_charge", uselist=False))

    class FinancePayment(db.Model):
        __tablename__ = "finance_payment"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
        membership_id = db.Column(db.Integer, db.ForeignKey("membership.id", ondelete="RESTRICT"))
        user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
        amount_cents = db.Column(db.Integer, nullable=False)
        method = db.Column(db.String(20), nullable=False)
        reference = db.Column(db.String(120))
        note = db.Column(db.Text)
        received_at = db.Column(db.DateTime, nullable=False)
        recorded_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        voided_at = db.Column(db.DateTime)
        voided_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        void_reason = db.Column(db.Text)
        __table_args__ = (
            db.CheckConstraint("membership_id IS NOT NULL OR user_id IS NOT NULL", name="finance_payment_owner_required"),
            db.CheckConstraint("amount_cents > 0", name="finance_payment_amount_positive"),
            db.CheckConstraint("method IN ('bank_transfer', 'cash', 'other')", name="finance_payment_method_valid"),
            db.Index("ix_finance_payment_membership_received", "membership_id", "received_at"),
            db.Index("ix_finance_payment_user_received", "user_id", "received_at"),
        )

    class FinanceChargeStatusHistory(db.Model):
        __tablename__ = "finance_charge_status_history"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        charge_id = db.Column(db.Integer, db.ForeignKey("finance_charge.id", ondelete="CASCADE"), nullable=False)
        from_status = db.Column(db.String(20))
        to_status = db.Column(db.String(20), nullable=False)
        changed_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        changed_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        note = db.Column(db.Text)
        __table_args__ = (db.Index("ix_finance_charge_status_history_charge", "charge_id", "changed_at"),)

    class FinancePaymentAllocation(db.Model):
        __tablename__ = "finance_payment_allocation"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        payment_id = db.Column(db.Integer, db.ForeignKey("finance_payment.id", ondelete="RESTRICT"), nullable=False)
        charge_id = db.Column(db.Integer, db.ForeignKey("finance_charge.id", ondelete="RESTRICT"), nullable=False)
        amount_cents = db.Column(db.Integer, nullable=False, default=0)
        created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        updated_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        __table_args__ = (
            db.CheckConstraint("amount_cents >= 0", name="finance_payment_allocation_amount_nonnegative"),
            db.UniqueConstraint("payment_id", "charge_id", name="finance_payment_allocation_payment_charge_key"),
            db.Index("ix_finance_payment_allocation_charge", "charge_id", "amount_cents"),
            db.Index("ix_finance_payment_allocation_payment", "payment_id", "amount_cents"),
        )

    class FinancePaymentAllocationHistory(db.Model):
        __tablename__ = "finance_payment_allocation_history"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        allocation_id = db.Column(db.Integer, db.ForeignKey("finance_payment_allocation.id", ondelete="CASCADE"), nullable=False)
        from_amount_cents = db.Column(db.Integer, nullable=False)
        to_amount_cents = db.Column(db.Integer, nullable=False)
        changed_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        changed_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        source = db.Column(db.String(32), nullable=False)
        note = db.Column(db.Text)
        __table_args__ = (
            db.CheckConstraint("from_amount_cents >= 0", name="finance_payment_allocation_history_from_nonnegative"),
            db.CheckConstraint("to_amount_cents >= 0", name="finance_payment_allocation_history_to_nonnegative"),
            db.Index("ix_finance_payment_allocation_history", "allocation_id", "changed_at"),
        )

    class FinanceChargeAdjustmentHistory(db.Model):
        __tablename__ = "finance_charge_adjustment_history"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        charge_id = db.Column(db.Integer, db.ForeignKey("finance_charge.id", ondelete="CASCADE"), nullable=False)
        billing_run_id = db.Column(db.Integer, db.ForeignKey("finance_billing_run.id", ondelete="SET NULL"))
        cycle_year = db.Column(db.Integer, nullable=False)
        from_amount_cents = db.Column(db.Integer, nullable=False)
        to_amount_cents = db.Column(db.Integer, nullable=False)
        from_fee_category = db.Column(db.String(20))
        to_fee_category = db.Column(db.String(20))
        from_name = db.Column(db.String(100), nullable=False)
        to_name = db.Column(db.String(100), nullable=False)
        from_due_date = db.Column(db.Date)
        to_due_date = db.Column(db.Date)
        changed_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        changed_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        source = db.Column(db.String(32), nullable=False)
        note = db.Column(db.Text)
        __table_args__ = (
            db.CheckConstraint("from_amount_cents >= 0", name="finance_charge_adjustment_from_nonnegative"),
            db.CheckConstraint("to_amount_cents >= 0", name="finance_charge_adjustment_to_nonnegative"),
            db.Index("ix_finance_charge_adjustment_charge", "charge_id", "changed_at"),
        )

    class FinanceReminder(db.Model):
        __tablename__ = "finance_reminder"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        batch_uid = db.Column(UUID(as_uuid=True), nullable=False)
        membership_id = db.Column(db.Integer, db.ForeignKey("membership.id", ondelete="RESTRICT"))
        user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
        email_snapshot = db.Column(db.String(255), nullable=False)
        balance_snapshot_cents = db.Column(db.Integer, nullable=False)
        sent_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        sent_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        __table_args__ = (
            db.CheckConstraint("membership_id IS NOT NULL OR user_id IS NOT NULL", name="finance_reminder_owner_required"),
            db.Index("ix_finance_reminder_batch", "batch_uid"),
            db.Index("ix_finance_reminder_user", "user_id", "sent_at"),
        )

    class FinanceSettings(db.Model):
        __tablename__ = "finance_settings"
        id = db.Column(db.Integer, primary_key=True)
        payment_instructions = db.Column(db.Text, nullable=False, default="")
        mail_test_email = db.Column(db.String(255), nullable=False, default="")
        updated_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    class FinanceMailDraft(db.Model):
        __tablename__ = "finance_mail_draft"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        kind = db.Column(db.String(32), nullable=False, unique=True)
        subject_template = db.Column(db.String(255), nullable=False)
        body_template = db.Column(db.Text, nullable=False)
        minimum_balance_cents = db.Column(db.Integer, nullable=False, default=0)
        cycle_year = db.Column(db.Integer)
        selected_recipient_keys = db.Column(db.JSON)
        version = db.Column(db.Integer, nullable=False, default=1)
        updated_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        __table_args__ = (
            db.CheckConstraint(
                "kind IN ('payment_reminder', 'student_verification')",
                name="finance_mail_draft_kind_valid",
            ),
            db.CheckConstraint("minimum_balance_cents >= 0", name="finance_mail_draft_threshold_nonnegative"),
            db.CheckConstraint("version > 0", name="finance_mail_draft_version_positive"),
        )

    class FinanceMailCampaign(db.Model):
        __tablename__ = "finance_mail_campaign"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
        kind = db.Column(db.String(32), nullable=False)
        source = db.Column(db.String(20), nullable=False, default="admin")
        cycle_year = db.Column(db.Integer)
        minimum_balance_cents = db.Column(db.Integer)
        test_only = db.Column(db.Boolean, nullable=False, default=False)
        subject_template = db.Column(db.String(255), nullable=False)
        body_template = db.Column(db.Text, nullable=False)
        created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        status = db.Column(db.String(24), nullable=False, default="sending")
        counts = db.Column(db.JSON)
        completed_at = db.Column(db.DateTime)
        recipients = db.relationship(
            "FinanceMailRecipient",
            cascade="all, delete-orphan",
            backref="campaign",
            lazy="select",
            order_by="FinanceMailRecipient.id",
        )
        __table_args__ = (
            db.CheckConstraint(
                "kind IN ('payment_reminder', 'student_verification')",
                name="finance_mail_campaign_kind_valid",
            ),
            db.CheckConstraint("minimum_balance_cents IS NULL OR minimum_balance_cents >= 0", name="finance_mail_campaign_threshold_nonnegative"),
            db.Index("ix_finance_mail_campaign_kind_created", "kind", "created_at"),
        )

    class FinanceMailRecipient(db.Model):
        __tablename__ = "finance_mail_recipient"
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        campaign_id = db.Column(db.Integer, db.ForeignKey("finance_mail_campaign.id", ondelete="CASCADE"), nullable=False)
        recipient_key = db.Column(db.String(100), nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
        membership_id = db.Column(db.Integer, db.ForeignKey("membership.id", ondelete="SET NULL"))
        username_snapshot = db.Column(db.String(80), nullable=False, default="")
        display_name_snapshot = db.Column(db.String(160), nullable=False, default="")
        email_snapshot = db.Column(db.String(255))
        balance_snapshot_cents = db.Column(db.Integer)
        activity_snapshot = db.Column(db.JSON)
        status = db.Column(db.String(24), nullable=False)
        reason = db.Column(db.Text)
        error_message = db.Column(db.Text)
        subject_snapshot = db.Column(db.String(255))
        body_snapshot = db.Column(db.Text)
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
        attempted_at = db.Column(db.DateTime)
        completed_at = db.Column(db.DateTime)
        __table_args__ = (
            db.CheckConstraint(
                "status IN ('queued', 'accepted', 'failed', 'skipped', 'excluded', 'legacy_attempted')",
                name="finance_mail_recipient_status_valid",
            ),
            db.UniqueConstraint("campaign_id", "recipient_key", name="finance_mail_recipient_campaign_key"),
            db.Index("ix_finance_mail_recipient_campaign_status", "campaign_id", "status"),
        )

    class HowTo(db.Model):
        __tablename__ = 'howto'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        userFK = db.Column(db.Integer, db.ForeignKey("user.id",ondelete="SET DEFAULT"),default=1)
        header = db.Column(db.TEXT)
        body = db.Column(db.TEXT)
        created = db.Column(db.DateTime)
        last_changed = db.Column(db.DateTime)
        visibility = db.Column(db.String(10))







    
def init_database():
    if os.getenv("DROP_AND_CREATE_DATABASE")=="true":
        db.drop_all()
        db.create_all()
        print("--- DROP_AND_CREATE_DATABASE \t true ---")
        print("--- DROPPING SHOULDNT BE USED ANYMOR ---")
    else:
        print("--- DROP_AND_CREATE_DATABASE \t false ---") 

def init_roles():
    print("--- Initializing roles \t\t ---")
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        roles_path = os.path.join(script_dir, "roles.json")
        with open(roles_path, "r") as f:
            roles = json.load(f)
            requestable_on_change = set(roles.get("requestable_on_change", []))
            for name, perm in roles.get("public").items():
                role = Tables.Role.query.filter_by(name=name).first()
                permissions = perm if perm else []
                if role:
                    role.name=name
                    role.permissions=permissions
                    role.selectable_on_register="yes"
                    role.requestable_on_change=name in requestable_on_change
                    print(f"--- role '{name}' already exists, permission update ---")
                else:
                    
                    new_role = Tables.Role(
                        name=name,
                        permissions=permissions,
                        selectable_on_register="yes",
                        requestable_on_change=name in requestable_on_change,
                    )
                    db.session.add(new_role)
                    print(f"--- role '{name}' initialized ---")
            
            for name, perm in roles.get("private").items():
                role = Tables.Role.query.filter_by(name=name).first()
                permissions = perm if perm else []
                if role:
                    role.name=name
                    role.permissions=permissions
                    role.selectable_on_register="no"
                    role.requestable_on_change=name in requestable_on_change
                    print(f"--- role '{name}' already exists, permission update ---")
                else:
                     
                    new_role = Tables.Role(
                        name=name,
                        permissions=permissions,
                        selectable_on_register="no",
                        requestable_on_change=name in requestable_on_change,
                    )
                    db.session.add(new_role)
                    print(f"--- role '{name}' initialized ---")
        db.session.commit()
    except Exception as e:
        print("--- init_roles() ERROR:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

def init_default_role():
    if os.getenv("CREATE_ADMIN")=="true":
        print("--- CREATE_ADMIN \t\t true ---")
        admin_pwd = secrets.token_hex(12)
        hashed_password = bcrypt.generate_password_hash(admin_pwd).decode('utf-8')
        admin_existing = Tables.User.query.filter_by(username="admin").first()
        if admin_existing:
            admin_existing.password = hashed_password
            print(f"--- Admin exists, new password: {admin_pwd} ---")
        else:
            admin = Tables.User(username="admin", password=hashed_password, role="Admin", permissions=[])
            db.session.add(admin)
            print(f"--- Admin generated: admin: {admin_pwd} ---")
        db.session.commit()
    else:
        print("--- CREATE_ADMIN \t\t false ---")


if os.getenv("SKIP_STARTUP_DATA") != "true":
    with app.app_context():
        init_database()
        init_roles()
        init_default_role()
