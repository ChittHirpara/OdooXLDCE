from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .booking import BOOKING_DURATION, CLUB_TZ, FRIDAY, SLOT_MINUTES


class Court(models.Model):
    _name = 'club.court'
    _description = 'Club Court'
    _order = 'sport, name'

    name = fields.Char(required=True)
    sport = fields.Selection([('tennis', 'Tennis'), ('cricket', 'Cricket')], required=True)
    list_price = fields.Float(string='List Price / Hour', required=True,
                              help="Full price per hour, charged to walk-ins and non-active members.")
    social_capacity = fields.Integer(
        default=8, help="Maximum players sharing this court in one slot on Friday social play.")
    open_hour = fields.Float(default=6.0, help="Opening time, club timezone (e.g. 6.5 = 06:30).")
    close_hour = fields.Float(default=22.0, help="Closing time, club timezone.")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('list_price_positive', 'CHECK(list_price >= 0)', 'List price cannot be negative.'),
        ('capacity_positive', 'CHECK(social_capacity > 0)', 'Social capacity must be at least 1.'),
    ]

    def get_availability(self, day):
        """Bookable 1-hour slots of these courts for a club-local date.

        Returns one dict per court with a slot every 30 minutes. On Friday
        (social play) ``places_left`` is the free player capacity; on other
        days it is 1 if the court is free and 0 if not.
        """
        day_start = CLUB_TZ.localize(datetime.combine(day, time.min))
        to_utc = lambda dt: dt.astimezone(pytz.utc).replace(tzinfo=None)  # noqa: E731
        bookings = self.env['club.booking'].search([
            ('court_id', 'in', self.ids),
            ('state', '!=', 'cancelled'),
            ('start_datetime', '>', to_utc(day_start) - BOOKING_DURATION),
            ('start_datetime', '<', to_utc(day_start + timedelta(days=1))),
        ])
        is_social = day.weekday() == FRIDAY
        half = timedelta(minutes=SLOT_MINUTES)
        result = []
        for court in self:
            court_bookings = bookings.filtered(lambda b: b.court_id == court)
            slots = []
            minutes = round(court.open_hour * 60)
            while minutes + 60 <= round(court.close_hour * 60):
                local = day_start + timedelta(minutes=minutes)
                start, end = to_utc(local), to_utc(local) + BOOKING_DURATION
                overlapping = court_bookings.filtered(
                    lambda b: b.start_datetime < end and b.end_datetime > start)
                if is_social:
                    taken = max(
                        sum(overlapping.filtered(
                            lambda b: b.start_datetime <= moment < b.end_datetime).mapped('players'))
                        for moment in (start, start + half))
                    places_left = max(court.social_capacity - taken, 0)
                else:
                    places_left = 0 if overlapping else 1
                slots.append({
                    'start': local.strftime('%H:%M'),
                    'end': (local + BOOKING_DURATION).strftime('%H:%M'),
                    'available': places_left > 0,
                    'places_left': places_left,
                })
                minutes += SLOT_MINUTES
            result.append({
                'court_id': court.id,
                'court': court.name,
                'sport': court.sport,
                'date': day.isoformat(),
                'is_social': is_social,
                'capacity': court.social_capacity if is_social else 1,
                'list_price': court.list_price,
                'slots': slots,
            })
        return result

    @api.constrains('open_hour', 'close_hour')
    def _check_hours(self):
        for court in self:
            if not 0 <= court.open_hour < court.close_hour <= 24:
                raise ValidationError("Opening hours of %s must be within 00:00-24:00 and open before close."
                                      % court.name)
            if court.close_hour - court.open_hour < 1:
                raise ValidationError("%s must be open at least one hour." % court.name)
