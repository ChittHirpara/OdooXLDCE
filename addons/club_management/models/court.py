from odoo import api, fields, models
from odoo.exceptions import ValidationError


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

    @api.constrains('open_hour', 'close_hour')
    def _check_hours(self):
        for court in self:
            if not 0 <= court.open_hour < court.close_hour <= 24:
                raise ValidationError("Opening hours of %s must be within 00:00-24:00 and open before close."
                                      % court.name)
            if court.close_hour - court.open_hour < 1:
                raise ValidationError("%s must be open at least one hour." % court.name)
