from datetime import timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

CLUB_TZ = pytz.timezone('Asia/Kolkata')
SLOT_MINUTES = 30
BOOKING_DURATION = timedelta(hours=1)
FRIDAY = 4
MAX_BOOKINGS_PER_DAY = 2


def to_club_time(dt):
    """Convert a naive UTC datetime (as stored by Odoo) to club-local time."""
    return pytz.utc.localize(dt).astimezone(CLUB_TZ)


class Booking(models.Model):
    _name = 'club.booking'
    _description = 'Court Booking'
    _inherit = ['mail.thread']
    _order = 'start_datetime desc, id desc'

    name = fields.Char(default='New', copy=False, readonly=True)
    court_id = fields.Many2one('club.court', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Member / Customer', tracking=True)
    walkin_name = fields.Char(string='Walk-in Name')
    start_datetime = fields.Datetime(string='Start', required=True, tracking=True)
    end_datetime = fields.Datetime(string='End', compute='_compute_times', store=True)
    booking_date = fields.Date(compute='_compute_times', store=True, string='Date (club time)')
    is_social = fields.Boolean(compute='_compute_times', store=True, string='Friday Social Play')
    players = fields.Integer(default=1)
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled'), ('done', 'Done')],
        default='draft', required=True, tracking=True)

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
            else:
                booking.end_datetime = False
                booking.booking_date = False
                booking.is_social = False

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
        self.state = 'cancelled'

    def action_done(self):
        self._require_state('confirmed')
        self.state = 'done'

    def action_draft(self):
        self._require_state('cancelled')
        self.state = 'draft'

    def action_reschedule(self, new_start, court=None):
        """Move a booking to a new start time (and optionally another court).

        All constraints are re-checked by the write.
        """
        self._require_state('draft', 'confirmed')
        for booking in self:
            vals = {'start_datetime': new_start}
            if court:
                vals['court_id'] = court.id
            booking.write(vals)
            booking.message_post(body="Booking rescheduled.")
        return True

    def _require_state(self, *states):
        for booking in self:
            if booking.state not in states:
                raise UserError("Booking %s is %s; this action needs it to be %s."
                                % (booking.name, booking.state, " or ".join(states)))
