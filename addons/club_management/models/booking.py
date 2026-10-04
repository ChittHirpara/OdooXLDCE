import re
import uuid
from datetime import datetime, timedelta

import pytz

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import email_normalize

CLUB_TZ = pytz.timezone('Asia/Kolkata')
SLOT_MINUTES = 30
BOOKING_DURATION = timedelta(hours=1)
FRIDAY = 4
MAX_BOOKINGS_PER_DAY = 2
WEBSITE_BOOKING_DAYS = 14        # how far ahead a visitor may book online


def to_club_time(dt):
    """Convert a naive UTC datetime (as stored by Odoo) to club-local time."""
    return pytz.utc.localize(dt).astimezone(CLUB_TZ)


def club_today():
    """Today's date in club time (not the server's or the user's timezone)."""
    return to_club_time(fields.Datetime.now()).date()


class Booking(models.Model):
    _name = 'club.booking'
    _description = 'Court Booking'
    _inherit = ['mail.thread']
    _order = 'start_datetime desc, id desc'

    name = fields.Char(default='New', copy=False, readonly=True)
    court_id = fields.Many2one('club.court', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Member / Customer', tracking=True)
    walkin_name = fields.Char(string='Walk-in Name')
    guest_phone = fields.Char(string='Guest Phone', help="Contact of a guest who booked online.")
    guest_email = fields.Char(string='Guest Email', help="Contact of a guest who booked online.")
    booking_source = fields.Selection(
        [('staff', 'Front desk / screens'), ('website', 'Website')], default='staff', required=True)
    access_token = fields.Char(copy=False, readonly=True, index=True,
                               help="Secret in the visitor's booking link (view and cancel).")
    start_datetime = fields.Datetime(string='Start', required=True, tracking=True)
    end_datetime = fields.Datetime(string='End', compute='_compute_times', store=True)
    booking_date = fields.Date(compute='_compute_times', store=True, string='Date (club time)')
    is_social = fields.Boolean(compute='_compute_times', store=True, string='Friday Social Play')
    players = fields.Integer(default=1)
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled'), ('done', 'Done')],
        default='draft', required=True, tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    price = fields.Monetary(compute='_compute_price', store=True, tracking=True)
    # Reporting dimensions (stored so pivot/graph can group by them)
    tier = fields.Selection(
        [('gold', 'Gold'), ('silver', 'Silver'), ('junior', 'Junior'), ('guest', 'Walk-in / Non-member')],
        compute='_compute_price', store=True, string='Customer Tier')
    sport = fields.Selection(related='court_id.sport', store=True)
    start_hour = fields.Integer(compute='_compute_times', store=True, group_operator=False,
                                string='Start Hour (club time)')
    invoice_id = fields.Many2one('account.move', string='Invoice', copy=False, readonly=True)

    _sql_constraints = [
        ('players_positive', 'CHECK(players > 0)', 'A booking needs at least one player.'),
    ]

    @api.depends('start_datetime')
    def _compute_times(self):
        for booking in self:
            if booking.start_datetime:
                local = to_club_time(booking.start_datetime)
                booking.end_datetime = booking.start_datetime + BOOKING_DURATION
                booking.booking_date = local.date()
                booking.is_social = local.weekday() == FRIDAY
                booking.start_hour = local.hour
            else:
                booking.end_datetime = False
                booking.booking_date = False
                booking.is_social = False
                booking.start_hour = False

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------
    def _get_member_plan(self):
        """Plan whose rate applies: the partner must be a member whose
        membership is still valid on the booking date. Otherwise empty."""
        self.ensure_one()
        partner = self.partner_id
        if (partner.is_member and partner.plan_id and partner.expiry_date
                and self.booking_date and partner.expiry_date >= self.booking_date):
            return partner.plan_id
        return self.env['club.membership.plan']

    @api.depends('court_id.list_price', 'booking_date', 'partner_id.is_member',
                 'partner_id.plan_id.court_rate', 'partner_id.expiry_date')
    def _compute_price(self):
        for booking in self:
            plan = booking._get_member_plan()
            booking.price = plan.court_rate if plan else booking.court_id.list_price
            booking.tier = plan.code if plan else 'guest'

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('partner_id', 'walkin_name')
    def _check_customer(self):
        for booking in self:
            if not booking.partner_id and not booking.walkin_name:
                raise ValidationError("Select a member or enter a walk-in name.")

    @api.constrains('start_datetime', 'court_id')
    def _check_slot(self):
        for booking in self:
            local = to_club_time(booking.start_datetime)
            if local.minute % SLOT_MINUTES or local.second:
                raise ValidationError(
                    "Bookings must start on the hour or half hour (got %s)." % local.strftime('%H:%M'))
            start_hour = local.hour + local.minute / 60
            court = booking.court_id
            if start_hour < court.open_hour or start_hour + 1 > court.close_hour:
                raise ValidationError(
                    "%s is only open %02d:%02d-%02d:%02d, so a 1-hour booking cannot start at %s."
                    % (court.name, *divmod(round(court.open_hour * 60), 60),
                       *divmod(round(court.close_hour * 60), 60), local.strftime('%H:%M')))

    @api.constrains('start_datetime', 'court_id', 'players', 'state')
    def _check_availability(self):
        active = self.filtered(lambda b: b.state != 'cancelled')
        if not active:
            return
        # Serialise concurrent bookings on the same court so two transactions
        # cannot both pass the overlap check.
        self.env.cr.execute(
            'SELECT id FROM club_court WHERE id IN %s FOR UPDATE', (tuple(active.court_id.ids),))
        for booking in active:
            others = self.search([
                ('court_id', '=', booking.court_id.id),
                ('id', '!=', booking.id),
                ('state', '!=', 'cancelled'),
                ('start_datetime', '<', booking.end_datetime),
                ('end_datetime', '>', booking.start_datetime),
            ])
            when = to_club_time(booking.start_datetime).strftime('%a %d %b %H:%M')
            if not booking.is_social:
                if others:
                    raise ValidationError(
                        "%s is already booked at %s (%s)." % (booking.court_id.name, when, others[0].name))
                continue
            capacity = booking.court_id.social_capacity
            half = timedelta(minutes=SLOT_MINUTES)
            for moment in (booking.start_datetime, booking.start_datetime + half):
                taken = sum(others.filtered(
                    lambda o: o.start_datetime <= moment < o.end_datetime).mapped('players'))
                if taken + booking.players > capacity:
                    raise ValidationError(
                        "Social play on %s is full at %s: %s of %s places taken, %s requested."
                        % (booking.court_id.name, when, taken, capacity, booking.players))

    @api.constrains('partner_id', 'start_datetime', 'state')
    def _check_daily_limit(self):
        for booking in self.filtered(lambda b: b.partner_id and b.state != 'cancelled'):
            count = self.search_count([
                ('partner_id', '=', booking.partner_id.id),
                ('booking_date', '=', booking.booking_date),
                ('state', '!=', 'cancelled'),
            ])
            if count > MAX_BOOKINGS_PER_DAY:
                raise ValidationError(
                    "%s already has %s bookings on %s (maximum per day)."
                    % (booking.partner_id.name, MAX_BOOKINGS_PER_DAY, booking.booking_date))

    @api.constrains('guest_phone', 'guest_email', 'start_datetime', 'state')
    def _check_guest_daily_limit(self):
        """A guest who booked online (no member record) gets the same two-a-day limit,
        counted by phone number or e-mail so changing the name does not get round it."""
        for booking in self.filtered(lambda b: not b.partner_id and b.state != 'cancelled'
                                     and (b.guest_phone or b.guest_email)):
            contact = []
            if booking.guest_phone:
                contact.append(('guest_phone', '=', booking.guest_phone))
            if booking.guest_email:
                contact.append(('guest_email', '=', booking.guest_email))
            domain = [('partner_id', '=', False), ('booking_date', '=', booking.booking_date),
                      ('state', '!=', 'cancelled')] + ['|'] * (len(contact) - 1) + contact
            if self.search_count(domain) > MAX_BOOKINGS_PER_DAY:
                raise ValidationError(
                    "You already have %s bookings on %s (maximum per day). "
                    "Cancel one first, or choose another day." % (MAX_BOOKINGS_PER_DAY, booking.booking_date))

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('club.booking') or 'New'
        return super().create(vals_list)

    def action_confirm(self):
        self._require_state('draft')
        self.state = 'confirmed'

    def action_cancel(self):
        self._require_state('draft', 'confirmed')
        for booking in self:
            if booking.invoice_id.state == 'posted':
                raise UserError(
                    "Booking %s has a posted invoice (%s). Issue a credit note before cancelling."
                    % (booking.name, booking.invoice_id.name))
        self.state = 'cancelled'
        self._send_cancellation()

    def _send_cancellation(self):
        template = self.env.ref('club_management.mail_template_booking_cancelled', raise_if_not_found=False)
        for booking in self:
            if template and (booking.partner_id.email or booking.guest_email):
                template.sudo().send_mail(booking.id)

    def action_create_invoice(self):
        """Create a draft customer invoice for the booking price.

        Walk-ins without a contact are invoiced to the shared "Walk-in Customer".
        """
        product = self.env.ref('club_management.product_court_booking')
        walkin_partner = self.env.ref('club_management.partner_walkin')
        for booking in self:
            if booking.state == 'cancelled':
                raise UserError("Booking %s is cancelled and cannot be invoiced." % booking.name)
            if booking.invoice_id:
                raise UserError("Booking %s is already invoiced (%s)."
                                % (booking.name, booking.invoice_id.name))
            local = to_club_time(booking.start_datetime)
            label = "%s - %s %s-%s" % (
                booking.court_id.name, local.strftime('%a %d %b %Y'),
                local.strftime('%H:%M'), (local + BOOKING_DURATION).strftime('%H:%M'))
            if not booking.partner_id:
                label += " (%s)" % booking.walkin_name
            booking.invoice_id = self.env['account.move'].with_company(booking.company_id).create({
                'move_type': 'out_invoice',
                'club_source': 'court',
                'partner_id': (booking.partner_id or walkin_partner).id,
                'invoice_origin': booking.name,
                'invoice_line_ids': [Command.create({
                    'product_id': product.id,
                    'name': label,
                    'quantity': 1,
                    'price_unit': booking.price,
                })],
            })
        return True

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }

    def action_done(self):
        self._require_state('confirmed')
        self.state = 'done'

    def action_draft(self):
        self._require_state('cancelled')
        self.state = 'draft'

    def action_reschedule(self, new_start, court=None):
        """Move a booking to a new start time (and optionally another court).

        All booking rules are re-checked by the write. An invoiced booking may
        only move if its price stays the same.
        """
        self._require_state('draft', 'confirmed')
        for booking in self:
            before = "%s, %s" % (
                booking.court_id.name, to_club_time(booking.start_datetime).strftime('%a %d %b %H:%M'))
            old_price = booking.price
            vals = {'start_datetime': new_start}
            if court:
                vals['court_id'] = court.id
            booking.write(vals)
            if booking.invoice_id and booking.price != old_price:
                raise UserError(
                    "Moving booking %s would change its price from %s to %s, but it is already "
                    "invoiced (%s). Cancel the invoice or create a new booking instead."
                    % (booking.name, old_price, booking.price, booking.invoice_id.name))
            booking.message_post(body="Rescheduled from %s to %s, %s." % (
                before, booking.court_id.name,
                to_club_time(booking.start_datetime).strftime('%a %d %b %H:%M')))
        return True

    def action_open_reschedule(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reschedule Booking',
            'res_model': 'club.booking.reschedule',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_booking_id': self.id},
        }

    def _require_state(self, *states):
        for booking in self:
            if booking.state not in states:
                raise UserError("Booking %s is %s; this action needs it to be %s."
                                % (booking.name, booking.state, " or ".join(states)))

    # ------------------------------------------------------------------
    # Frontend RPC & Integration APIs
    # ------------------------------------------------------------------
    @api.model
    def calculate_booking_price(self, court_id, date_str, time_str, partner_id=None):
        """Authoritative backend price calculation for court booking."""
        court = self.env['club.court'].browse(int(court_id))
        if not court.exists():
            raise ValidationError("Court not found.")

        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            booking_date = club_today()

        plan = None
        if partner_id:
            partner = self.env['res.partner'].browse(int(partner_id))
            if partner.exists() and partner.is_member and partner.plan_id and partner.expiry_date:
                if partner.expiry_date >= booking_date:
                    plan = partner.plan_id

        price = plan.court_rate if plan else court.list_price
        tier = plan.code if plan else 'guest'
        plan_name = plan.name if plan else 'Walk-in / Guest'

        return {
            'price': price,
            'formatted_price': f"₹{int(price)}",
            'tier': tier,
            'plan_name': plan_name,
            'court_name': court.name,
            'court_rate': court.list_price,
        }

    @api.model
    def create_member_booking(self, court_id, date_str, time_str, partner_id=None, walkin_name=None, players=1):
        """Create and confirm a booking directly from frontend or client action."""
        court = self.env['club.court'].browse(int(court_id))
        if not court.exists():
            raise ValidationError("Court not found.")

        try:
            b_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            h, m = [int(x) for x in time_str.split(':')]
            local_dt = CLUB_TZ.localize(datetime.combine(b_date, datetime.min.time())).replace(hour=h, minute=m)
            utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
        except Exception as e:
            raise ValidationError(f"Invalid date/time format: {e}")

        vals = {
            'court_id': court.id,
            'start_datetime': utc_dt,
            'players': max(1, int(players)),
        }

        if partner_id is not None and int(partner_id) > 0:
            partner = self.env['res.partner'].browse(int(partner_id)).exists()
            if not partner:
                raise ValidationError("Member not found. Please reload the page and try again.")
            vals['partner_id'] = partner.id
        elif walkin_name or partner_id is not None:
            vals['walkin_name'] = walkin_name or 'Walk-in Guest'    # id 0 is the walk-in guest
        else:
            vals['partner_id'] = self.env.user.partner_id.id

        booking = self.create(vals)
        booking.action_confirm()
        return booking._to_frontend()

    def _to_frontend(self):
        """Booking as the OWL screens expect it: ``id`` is the reference, ``odoo_id`` the record."""
        self.ensure_one()
        local_start = to_club_time(self.start_datetime)
        local_end = to_club_time(self.end_datetime)
        return {
            'id': self.name,
            'odoo_id': self.id,
            'name': self.name,
            'court_id': self.court_id.id,
            'court_name': self.court_id.name,
            'date': local_start.strftime('%Y-%m-%d'),
            'start_time': local_start.strftime('%H:%M'),
            'end_time': local_end.strftime('%H:%M'),
            'price': f"₹{int(self.price)}",
            'member_name': self.partner_id.name if self.partner_id else self.walkin_name,
            'plan_name': f"{self.tier.capitalize()} Member" if self.tier != 'guest' else "Non-member",
            'state': self.state,
        }

    @api.model
    def get_availability(self, date_str=None, court_id=None):
        """Booked start times per court for a date: ``{court_id: ['10:00', ...]}``."""
        return self.env['club.court'].get_availability_matrix(date_str, court_id)['availability_map']

    @api.model
    def create_booking_api(self, court_id, date_str, time_str, partner_id=None, walkin_name=None, players=1):
        """Book from the court-booking screen. Rule violations come back as a message."""
        try:
            with self.env.cr.savepoint():
                booking = self.create_member_booking(
                    court_id, date_str, time_str, partner_id, walkin_name, players)
        except (ValidationError, UserError) as error:
            return {'success': False, 'message': error.args[0]}
        return {'success': True, 'booking': booking}

    @api.model
    def cancel_member_booking(self, booking_id, partner_id=None):
        """Cancel an existing court reservation."""
        domain = [('id', '=', int(booking_id))]
        if partner_id:
            domain.append(('partner_id', '=', int(partner_id)))
        booking = self.search(domain, limit=1)
        if not booking:
            # Check by reference name
            booking = self.search([('name', '=', str(booking_id))], limit=1)
        if not booking:
            raise ValidationError("Booking record not found.")

        booking.action_cancel()
        return {'success': True, 'booking_id': booking.id, 'name': booking.name}

    @api.model
    def get_partner_bookings(self, partner_id=None):
        """Retrieve booking history for a member."""
        domain = []
        if partner_id and int(partner_id) > 0:
            domain.append(('partner_id', '=', int(partner_id)))
        bookings = self.search(domain, order='start_datetime desc', limit=50)

        return [b._to_frontend() for b in bookings]

    # ------------------------------------------------------------------
    # Online booking by website visitors (no staff involved)
    # ------------------------------------------------------------------
    @api.model
    def _club_start_utc(self, date_str, time_str):
        """Club-local date and time strings ('2026-10-05', '18:30') as a naive UTC datetime."""
        try:
            day = datetime.strptime(date_str, '%Y-%m-%d').date()
            hour, minute = [int(x) for x in time_str.split(':')]
            local = CLUB_TZ.localize(datetime.combine(day, datetime.min.time())).replace(hour=hour, minute=minute)
        except (ValueError, TypeError, AttributeError):
            raise ValidationError("That date or time is not valid.")
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    @api.model
    def _check_public_window(self, start):
        """Online bookings: in the future, and no more than WEBSITE_BOOKING_DAYS ahead."""
        if start <= fields.Datetime.now():
            raise ValidationError("That time has already passed. Please pick a later slot.")
        if to_club_time(start).date() > club_today() + timedelta(days=WEBSITE_BOOKING_DAYS):
            raise ValidationError(
                "Online booking opens %s days ahead. Please pick an earlier day." % WEBSITE_BOOKING_DAYS)

    @api.model
    def create_public_booking(self, court_id, date_str, time_str, name, phone=None, email=None,
                              players=1, member_ref=None, member_email=None, member=None):
        """Book a court online, instantly confirmed, for a website visitor.

        A guest pays the court's list price. A member who gives their member ID and the
        e-mail on file pays their tier price. Every booking rule still applies. A booking
        made online can be viewed and cancelled with the private link in its e-mail.
        Raises ValidationError with a message the visitor can act on.
        """
        name = (name or '').strip()
        phone = re.sub(r'[^\d+]', '', phone or '')
        email = email_normalize((email or '').strip()) or False
        court = self.env['club.court'].sudo().browse(int(court_id or 0)).exists()
        if not court:
            raise ValidationError("That court does not exist.")
        start = self._club_start_utc(date_str, time_str)
        self._check_public_window(start)
        partner = self.env['res.partner']
        if member:      # a signed-in member: the website already knows who they are
            partner = member.sudo()
            name = partner.name
        elif member_ref:
            partner = self.env['res.partner']._club_verify_member(member_ref, member_email)
            name = partner.name
        else:
            if not name:
                raise ValidationError("Please tell us your name.")
            if not phone and not email:
                raise ValidationError("Please give a phone number or an e-mail address, so we can reach you.")
        try:
            players = max(1, min(int(players or 1), court.social_capacity))
        except (TypeError, ValueError):
            players = 1

        vals = {
            'court_id': court.id, 'start_datetime': start, 'players': players,
            'booking_source': 'website', 'access_token': uuid.uuid4().hex,
        }
        if partner:
            vals['partner_id'] = partner.id
        else:
            vals.update(walkin_name=name[:100], guest_phone=phone[:30] or False, guest_email=email)
        with self.env.cr.savepoint():       # a refused booking must leave nothing behind
            booking = self.sudo().with_context(mail_create_nolog=True).create(vals)
            booking.action_confirm()
        booking._send_confirmation()
        if not partner:
            booking._offer_membership_follow_up()
        return booking

    def _send_confirmation(self):
        template = self.env.ref('club_management.mail_template_booking_confirmed', raise_if_not_found=False)
        for booking in self:
            if template and (booking.partner_id.email or booking.guest_email):
                template.sudo().send_mail(booking.id)

    def _offer_membership_follow_up(self):
        """A guest who books online is a prospect: give the front desk a lead to offer a membership."""
        self.ensure_one()
        local = to_club_time(self.start_datetime)
        try:
            self.env['crm.lead'].create_club_enquiry(
                self.walkin_name, email=self.guest_email, phone=self.guest_phone,
                message="Booked %s on %s at %s online as a guest (%s). Offer a membership." % (
                    self.court_id.name, local.strftime('%a %d %b %Y'), local.strftime('%H:%M'), self.name),
                enquiry_type='court', sport=self.court_id.sport if self.court_id.sport in dict(
                    self.env['crm.lead']._fields['sport_interest'].selection) else None,
                notify=False)
        except ValidationError:
            pass                            # the booking stands even if the follow-up cannot be filed

    @api.model
    def get_by_token(self, token):
        token = (token or '').strip()
        return self.sudo().search([('access_token', '=', token)], limit=1) if len(token) >= 16 else self.browse()

    def cancel_by_visitor(self):
        """Cancel from the private link: allowed until the session starts, never once invoiced."""
        self.ensure_one()
        if self.state not in ('draft', 'confirmed'):
            raise ValidationError("This booking can no longer be cancelled.")
        if self.start_datetime <= fields.Datetime.now():
            raise ValidationError("This session has already started, so it cannot be cancelled online.")
        if self.invoice_id:
            raise ValidationError("This booking has been invoiced. Please contact the club to cancel it.")
        self.sudo().action_cancel()
        return True
