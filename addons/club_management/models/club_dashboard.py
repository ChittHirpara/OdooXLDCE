from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

from .booking import club_today

OPEN_HOURS_PER_DAY = 16     # courts open 06:00-22:00
SOURCES = [('membership', 'Memberships'), ('court', 'Court Bookings'),
           ('shop', 'Pro-Shop'), ('bar', 'Bar & Cafeteria')]
PERIODS = ('today', 'week', 'month', 'all')


class ClubDashboard(models.AbstractModel):
    """Numbers for the owner dashboard, always computed on the server."""
    _name = 'club.dashboard'
    _description = 'Owner Dashboard'

    @api.model
    def _period_dates(self, period):
        today = club_today()
        if period == 'today':
            return today, today
        if period == 'week':
            return today - timedelta(days=today.weekday()), today
        if period == 'month':
            return today.replace(day=1), today
        return None, None

    @api.model
    def get_dashboard_data(self, period='month'):
        if not self.env.user.has_group('club_management.group_club_manager'):
            raise AccessError("Only club managers can open the owner dashboard.")
        period = period if period in PERIODS else 'month'
        date_from, date_to = self._period_dates(period)
        env = self.sudo().env

        revenue = {key: 0.0 for key, _label in SOURCES}

        # Memberships: confirmed quotes for a plan product.
        domain = [('product_id', 'in', env['club.membership.plan'].search([]).product_id.ids),
                  ('order_id.state', '=', 'sale')]
        if date_from:
            domain += [('order_id.date_order', '>=', fields.Datetime.to_datetime(date_from)),
                       ('order_id.date_order', '<', fields.Datetime.to_datetime(date_to + timedelta(days=1)))]
        revenue['membership'] = sum(env['sale.order.line'].search(domain).mapped('price_subtotal'))

        # Courts: bookings that are not cancelled.
        booking_domain = [('state', '!=', 'cancelled')]
        if date_from:
            booking_domain += [('booking_date', '>=', date_from), ('booking_date', '<=', date_to)]
        bookings = env['club.booking'].search(booking_domain)
        revenue['court'] = sum(bookings.mapped('price'))

        # Shop and bar: orders taken through the club screens.
        order_domain = []
        if date_from:
            order_domain += [('create_date', '>=', fields.Datetime.to_datetime(date_from)),
                             ('create_date', '<', fields.Datetime.to_datetime(date_to + timedelta(days=1)))]
        orders = env['club.order'].search(order_domain)
        for channel in ('shop', 'bar'):
            revenue[channel] = sum(orders.filtered(lambda o: o.channel == channel).mapped('total'))

        total = sum(revenue.values())

        # Utilization: distinct booked court-hours against opening hours of all courts.
        courts = env['club.court'].search_count([])
        booked = len({(b.court_id.id, b.start_datetime) for b in bookings})
        if date_from:
            days = (date_to - date_from).days + 1
        else:
            dates = bookings.mapped('booking_date')
            days = ((max(dates) - min(dates)).days + 1) if dates else 1
        capacity = courts * OPEN_HOURS_PER_DAY * days
        utilization = min(100.0, round(100.0 * booked / capacity, 1)) if capacity else 0.0

        # Members.
        members = env['res.partner'].search([('is_member', '=', True), ('member_state', '=', 'active')])
        plans = [{'name': plan.name, 'count': len(members.filtered(lambda m: m.plan_id == plan))}
                 for plan in env['club.membership.plan'].search([])]

        # Outstanding: posted club invoices that are not fully paid.
        unpaid = env['account.move'].search([
            ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
            ('club_source', '!=', False), ('payment_state', 'in', ('not_paid', 'partial'))])

        currency = self.env.company.currency_id
        return {
            'period': period,
            'currency_symbol': currency.symbol,
            'total_revenue': total,
            'by_source': [{'key': key, 'label': label, 'amount': revenue[key],
                           'share': round(100.0 * revenue[key] / total, 1) if total else 0.0}
                          for key, label in SOURCES],
            'active_members': len(members),
            'members_by_plan': plans,
            'court_bookings': len(bookings),
            'court_utilization': utilization,
            'shop_sales': revenue['shop'],
            'bar_sales': revenue['bar'],
            'outstanding_amount': sum(unpaid.mapped('amount_residual')),
            'outstanding_count': len(unpaid),
        }
