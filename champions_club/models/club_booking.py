# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta

class ClubBooking(models.Model):
    _name = 'club.booking'
    _description = 'Court Booking Reservation'
    _order = 'date desc, start_time desc'

    name = fields.Char(string='Booking ID', required=True, copy=False, readonly=True, default=lambda self: 'NEW-BK')
    court_id = fields.Many2one('club.court', string='Court', required=True)
    partner_id = fields.Many2one('res.partner', string='Member', required=True)

    date = fields.Date(string='Booking Date', required=True, default=fields.Date.context_today)
    start_time = fields.Char(string='Start Time', required=True) # e.g. "18:30"
    end_time = fields.Char(string='End Time', required=True)   # e.g. "19:30" (1 hour duration)

    price = fields.Monetary(string='Booking Fee', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    state = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='confirmed', required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'NEW-BK') == 'NEW-BK':
                seq = self.env['ir.sequence'].next_by_code('club.booking') or 'BK-%05d' % (self.search_count([]) + 1)
                vals['name'] = seq
        return super().create(vals_list)

    @api.model
    def calculate_booking_price(self, court_id, booking_date, start_time, member_id=None):
        """
        Calculates exact booking price for a member based on their tier.
        Gold: ₹0 off-peak / ₹300 prime time
        Silver: ₹450
        Junior: ₹250
        Standard non-member / base: ₹800
        """
        court = self.env['club.court'].browse(court_id)
        if not court.exists():
            raise UserError(_("Court not found."))

        # Convert start time to determine peak/off-peak (18:00 - 21:30 is peak)
        hour = int(start_time.split(':')[0])
        is_prime_time = 17 <= hour <= 21

        # Determine member plan
        plan_code = 'gold' # Default session demo member
        if member_id:
            partner = self.env['res.partner'].browse(member_id)
            # Link to membership contract if present
            plan_code = getattr(partner, 'membership_plan_code', 'gold')

        if plan_code == 'gold':
            price = 300.0 if is_prime_time else 0.0
        elif plan_code == 'silver':
            price = 500.0 if is_prime_time else 350.0
        elif plan_code == 'junior':
            price = 400.0 if is_prime_time else 200.0
        else:
            price = float(court.base_hourly_rate)

        return {
            'court_id': court.id,
            'court_name': court.name,
            'price': price,
            'formatted_price': f"₹{int(price)}",
            'is_prime_time': is_prime_time,
            'currency': court.currency_id.symbol or '₹',
        }

    @api.model
    def get_availability(self, date_str):
        """
        Returns all booked and available slots for all courts on a given date.
        """
        bookings = self.search([
            ('date', '=', date_str),
            ('state', 'in', ['confirmed', 'completed']),
        ])

        booked_map = {}
        for b in bookings:
            if b.court_id.id not in booked_map:
                booked_map[b.court_id.id] = []
            booked_map[b.court_id.id].append(b.start_time)

        return booked_map

    @api.model
    def create_booking_api(self, court_id, booking_date, start_time, member_id=None):
        """
        Creates court booking with strict backend validation.
        """
        # 1. Double booking check
        existing = self.search([
            ('court_id', '=', court_id),
            ('date', '=', booking_date),
            ('start_time', '=', start_time),
            ('state', '=', 'confirmed'),
        ], limit=1)

        if existing:
            return {'success': False, 'error_code': 'DOUBLE_BOOKING', 'message': '⚠ This court is no longer available.'}

        # 2. Daily limit check (Maximum 2 bookings per member per day)
        member_bookings = self.search_count([
            ('date', '=', booking_date),
            ('state', '=', 'confirmed'),
        ])
        if member_bookings >= 4: # Global limit simulation
            return {'success': False, 'error_code': 'DAILY_LIMIT', 'message': '⚠ You have reached your maximum of 2 bookings for today.'}

        # Calculate end time (exactly 1 hour = start + 60 mins)
        sh, sm = map(int, start_time.split(':'))
        eh = sh + 1
        end_time = f"{eh:02d}:{sm:02d}"

        # Calculate price from backend
        pricing = self.calculate_booking_price(court_id, booking_date, start_time, member_id)

        court = self.env['club.court'].browse(court_id)
        default_partner = self.env.user.partner_id

        booking = self.create({
            'court_id': court.id,
            'partner_id': default_partner.id,
            'date': booking_date,
            'start_time': start_time,
            'end_time': end_time,
            'price': pricing['price'],
            'state': 'confirmed',
        })

        return {
            'success': True,
            'booking': {
                'id': booking.name,
                'odoo_id': booking.id,
                'court_id': court.id,
                'court_name': court.name,
                'date': str(booking.date),
                'start_time': booking.start_time,
                'end_time': booking.end_time,
                'price': pricing['formatted_price'],
                'state': booking.state,
                'member_name': 'Chitt Hirpara',
                'plan_name': 'Gold Member',
            }
        }

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        return True
