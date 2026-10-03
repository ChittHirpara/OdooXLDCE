from odoo import fields, models


class BookingReschedule(models.TransientModel):
    _name = 'club.booking.reschedule'
    _description = 'Reschedule a Court Booking'

    booking_id = fields.Many2one('club.booking', required=True, ondelete='cascade')
    current_start = fields.Datetime(related='booking_id.start_datetime', string='Current Start')
    court_id = fields.Many2one(
        'club.court', string='Court', required=True,
        default=lambda self: self.env['club.booking'].browse(
            self.env.context.get('default_booking_id')).court_id)
    new_start = fields.Datetime(
        string='New Start', required=True,
        default=lambda self: self.env['club.booking'].browse(
            self.env.context.get('default_booking_id')).start_datetime)

    def action_reschedule(self):
        self.ensure_one()
        court = self.court_id if self.court_id != self.booking_id.court_id else None
        self.booking_id.action_reschedule(self.new_start, court)
        return {'type': 'ir.actions.act_window_close'}
