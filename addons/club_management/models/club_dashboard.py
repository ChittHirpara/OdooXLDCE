from collections import defaultdict
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

from .booking import club_today

OPEN_HOURS_PER_DAY = 16     # courts open 06:00-22:00
SOURCES = [('membership', 'Memberships'), ('court', 'Court Bookings'),
           ('shop', 'Pro-Shop'), ('bar', 'Bar & Cafeteria')]
PERIODS = ('today', 'week', 'month', 'all')
PAYMENT_LABELS = {'cash': 'Cash', 'card': 'Card', 'upi': 'UPI', False: 'Paid at the club (method not recorded)'}
UTILIZATION_DAYS = 30
MAX_MONTHS = 24


def month_start(day, back=0):
    """First day of the month ``back`` months before ``day`` (negative goes forward)."""
    index = day.year * 12 + (day.month - 1) - back
    return date(index // 12, index % 12 + 1, 1)


def month_end(start):
    """Last day of the month that starts on ``start``."""
    return month_start(start, -1) - timedelta(days=1)


class ClubDashboard(models.AbstractModel):
    """Numbers for the owner dashboard, reports and staff overview, always computed on the server."""
    _name = 'club.dashboard'
    _description = 'Owner Dashboard'

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @api.model
    def _require_manager(self, what="the owner reports"):
        if not self.env.user.has_group('club_management.group_club_manager'):
            raise AccessError("Only club managers can open %s." % what)

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

    @staticmethod
    def _day_range(date_from, date_to):
        """Datetime bounds (inclusive start, exclusive end) for a date range."""
        return (fields.Datetime.to_datetime(date_from),
                fields.Datetime.to_datetime(date_to + timedelta(days=1)))

    @api.model
    def _revenue(self, date_from=None, date_to=None):
        """Revenue per source between two dates (inclusive); no dates means all time."""
        env = self.sudo().env
        revenue = {key: 0.0 for key, _label in SOURCES}

        # Memberships: confirmed quotes for a plan product.
        domain = [('product_id', 'in', env['club.membership.plan'].search([]).product_id.ids),
                  ('order_id.state', '=', 'sale')]
        if date_from:
            start, end = self._day_range(date_from, date_to)
            domain += [('order_id.date_order', '>=', start), ('order_id.date_order', '<', end)]
        revenue['membership'] = sum(env['sale.order.line'].search(domain).mapped('price_subtotal'))

        # Courts: bookings that are not cancelled.
        booking_domain = [('state', '!=', 'cancelled')]
        if date_from:
            booking_domain += [('booking_date', '>=', date_from), ('booking_date', '<=', date_to)]
        revenue['court'] = sum(env['club.booking'].search(booking_domain).mapped('price'))

        # Shop and bar: orders taken through the club screens.
        order_domain = []
        if date_from:
            start, end = self._day_range(date_from, date_to)
            order_domain += [('create_date', '>=', start), ('create_date', '<', end)]
        orders = env['club.order'].search(order_domain)
        for channel in ('shop', 'bar'):
            revenue[channel] = sum(orders.filtered(lambda o: o.channel == channel).mapped('total'))
        return revenue

    @api.model
    def _currency_symbol(self):
        return self.env.company.currency_id.symbol

    # ------------------------------------------------------------------
    # owner dashboard
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, period='month'):
        self._require_manager("the owner dashboard")
        period = period if period in PERIODS else 'month'
        date_from, date_to = self._period_dates(period)
        env = self.sudo().env
        today = club_today()

        revenue = self._revenue(date_from, date_to)
        total = sum(revenue.values())

        booking_domain = [('state', '!=', 'cancelled')]
        if date_from:
            booking_domain += [('booking_date', '>=', date_from), ('booking_date', '<=', date_to)]
        bookings = env['club.booking'].search(booking_domain)

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
        Partner = env['res.partner']
        members = Partner.search([('is_member', '=', True), ('member_state', '=', 'active')])
        expired = Partner.search_count([('is_member', '=', True), ('member_state', '=', 'expired')])
        plans = [{'name': plan.name, 'count': len(members.filtered(lambda m: m.plan_id == plan))}
                 for plan in env['club.membership.plan'].search([])]

        # Today, whatever period is chosen.
        todays_revenue = self._revenue(today, today)
        todays_bookings = env['club.booking'].search_count([
            ('booking_date', '=', today), ('state', '!=', 'cancelled')])

        # Outstanding: posted club invoices that are not fully paid.
        unpaid = env['account.move'].search([
            ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
            ('club_source', '!=', False), ('payment_state', 'in', ('not_paid', 'partial'))])

        return {
            'period': period,
            'currency_symbol': self._currency_symbol(),
            'total_revenue': total,
            'by_source': [{'key': key, 'label': label, 'amount': revenue[key],
                           'share': round(100.0 * revenue[key] / total, 1) if total else 0.0}
                          for key, label in SOURCES],
            'membership_revenue': revenue['membership'],
            'court_revenue': revenue['court'],
            'active_members': len(members),
            'expired_members': expired,
            'members_by_plan': plans,
            'court_bookings': len(bookings),
            'court_utilization': utilization,
            'todays_bookings': todays_bookings,
            'todays_sales': sum(todays_revenue.values()),
            'shop_sales': revenue['shop'],
            'bar_sales': revenue['bar'],
            'outstanding_amount': sum(unpaid.mapped('amount_residual')),
            'outstanding_count': len(unpaid),
        }

    # ------------------------------------------------------------------
    # reports and analytics
    # ------------------------------------------------------------------
    @api.model
    def get_analytics(self, months=6):
        """Everything on the Reports & Analytics screen, for the last ``months`` calendar months."""
        self._require_manager("the reports")
        try:
            months = max(1, min(int(months), MAX_MONTHS))
        except (TypeError, ValueError):
            months = 6
        env = self.sudo().env
        today = club_today()
        first = month_start(today, months - 1)
        start, end = self._day_range(first, today)
        orders = env['club.order'].search([('create_date', '>=', start), ('create_date', '<', end)])
        lines = orders.line_ids
        plans = env['club.membership.plan'].search([])
        total_all = lambda rev: sum(rev.values())   # noqa: E731

        # Monthly revenue, oldest first.
        monthly = []
        for back in range(months - 1, -1, -1):
            begin = month_start(today, back)
            rev = self._revenue(begin, min(month_end(begin), today))
            monthly.append({'month': begin.strftime('%b %Y'), 'total': total_all(rev), **rev})

        # Revenue by membership tier: plan fees, court bookings at that tier, shop and bar sales.
        by_plan = {plan.code: {'name': plan.name, 'membership': 0.0, 'court': 0.0, 'shop_bar': 0.0}
                   for plan in plans}
        by_plan['guest'] = {'name': 'Non-members', 'membership': 0.0, 'court': 0.0, 'shop_bar': 0.0}
        sale_lines = env['sale.order.line'].search([
            ('product_id', 'in', plans.product_id.ids), ('order_id.state', '=', 'sale'),
            ('order_id.date_order', '>=', start), ('order_id.date_order', '<', end)])
        for line in sale_lines:
            plan = plans.filtered(lambda p: p.product_id == line.product_id)[:1]
            by_plan[plan.code]['membership'] += line.price_subtotal
        for booking in env['club.booking'].search([
                ('state', '!=', 'cancelled'), ('booking_date', '>=', first), ('booking_date', '<=', today)]):
            by_plan[booking.tier if booking.tier in by_plan else 'guest']['court'] += booking.price
        for order in orders:
            by_plan[order.plan_id.code if order.plan_id.code in by_plan else 'guest']['shop_bar'] += order.total
        revenue_by_plan = [dict(row, total=row['membership'] + row['court'] + row['shop_bar'])
                           for row in by_plan.values()]

        # Court utilization over the last 30 days, per court.
        util_from = today - timedelta(days=UTILIZATION_DAYS - 1)
        bookings = env['club.booking'].search([
            ('state', '!=', 'cancelled'), ('booking_date', '>=', util_from), ('booking_date', '<=', today)])
        utilization = []
        for court in env['club.court'].search([]):
            booked = len({b.start_datetime for b in bookings if b.court_id == court})
            capacity = max(court.close_hour - court.open_hour, 1) * UTILIZATION_DAYS
            utilization.append({'court': court.name, 'sport': court.sport, 'hours': booked,
                                'percent': min(100.0, round(100.0 * booked / capacity, 1))})
        utilization.sort(key=lambda row: -row['percent'])

        # Best-selling products (shop and bar) by units.
        sold = defaultdict(lambda: {'qty': 0, 'amount': 0.0, 'channel': ''})
        for line in lines:
            sold[line.product_id]['channel'] = 'Bar' if line.order_id.channel == 'bar' else 'Shop'
            sold[line.product_id]['qty'] += line.qty
            sold[line.product_id]['amount'] += line.line_total
        best = sorted(sold.items(), key=lambda item: (-item[1]['qty'], -item[1]['amount']))[:10]
        best_sellers = [{'product': product.name, **data} for product, data in best]

        # Bar sales: totals, average ticket, top items and the last 14 days.
        bar_orders = orders.filtered(lambda o: o.channel == 'bar')
        bar_items = defaultdict(lambda: {'qty': 0, 'amount': 0.0})
        for line in bar_orders.line_ids:
            bar_items[line.product_id.name]['qty'] += line.qty
            bar_items[line.product_id.name]['amount'] += line.line_total
        daily = []
        for back in range(13, -1, -1):
            day = today - timedelta(days=back)
            day_start, day_end = self._day_range(day, day)
            daily.append({'day': day.strftime('%d %b'), 'amount': sum(
                o.total for o in bar_orders if day_start <= o.create_date < day_end)})
        bar_total = sum(bar_orders.mapped('total'))
        bar = {
            'total': bar_total, 'orders': len(bar_orders),
            'average': round(bar_total / len(bar_orders), 2) if bar_orders else 0.0,
            'top_items': [{'product': name, **data} for name, data in
                          sorted(bar_items.items(), key=lambda item: -item[1]['amount'])[:5]],
            'daily': daily,
        }

        # Payment methods of shop and bar orders.
        payments = defaultdict(lambda: {'count': 0, 'amount': 0.0})
        for order in orders:
            payments[order.payment_method or False]['count'] += 1
            payments[order.payment_method or False]['amount'] += order.total
        pay_total = sum(row['amount'] for row in payments.values())
        payment_methods = [{'method': PAYMENT_LABELS.get(method, str(method)), **row,
                            'share': round(100.0 * row['amount'] / pay_total, 1) if pay_total else 0.0}
                           for method, row in sorted(payments.items(), key=lambda item: -item[1]['amount'])]

        # Membership growth: joiners per month and the running total of members.
        members = env['res.partner'].search([('is_member', '=', True), ('join_date', '!=', False)])
        growth = []
        for back in range(months - 1, -1, -1):
            begin = month_start(today, back)
            last = month_end(begin)
            growth.append({
                'month': begin.strftime('%b %Y'),
                'joined': len(members.filtered(lambda m: begin <= m.join_date <= last)),
                'total': len(members.filtered(lambda m: m.join_date <= last))})

        return {
            'months': months,
            'currency_symbol': self._currency_symbol(),
            'monthly_revenue': monthly,
            'revenue_by_plan': revenue_by_plan,
            'court_utilization': utilization,
            'utilization_days': UTILIZATION_DAYS,
            'best_sellers': best_sellers,
            'bar': bar,
            'payment_methods': payment_methods,
            'membership_growth': growth,
        }

    # ------------------------------------------------------------------
    # staff
    # ------------------------------------------------------------------
    @api.model
    def get_staff_overview(self):
        """Staff users with what they have done, and the recent POS shifts."""
        self._require_manager("the staff overview")
        env = self.sudo().env
        staff_group = env.ref('club_management.group_club_staff')
        manager_group = env.ref('club_management.group_club_manager')
        users = env['res.users'].search([
            ('groups_id', 'in', staff_group.id), ('share', '=', False),
            ('id', '!=', env.ref('base.user_root').id)], order='name')
        Booking, Order, Lead = env['club.booking'], env['club.order'], env['crm.lead']
        Session = env['pos.session']
        staff = []
        for user in users:
            staff.append({
                'id': user.id, 'name': user.name, 'login': user.login,
                'role': 'Manager' if manager_group in user.groups_id else 'Staff',
                'last_login': fields.Datetime.to_string(user.login_date) if user.login_date else None,
                'bookings': Booking.search_count([('create_uid', '=', user.id)]),
                'orders': Order.search_count([('create_uid', '=', user.id)]),
                'leads': Lead.search_count([('user_id', '=', user.id)]),
                'shifts': Session.search_count([('user_id', '=', user.id)]),
            })
        shifts = [{
            'name': s.name, 'user': s.user_id.name, 'state': s.state,
            'start': fields.Datetime.to_string(s.start_at) if s.start_at else None,
            'stop': fields.Datetime.to_string(s.stop_at) if s.stop_at else None,
        } for s in Session.search([], order='id desc', limit=10)]
        return {'staff': staff, 'shifts': shifts, 'open_shifts': sum(1 for s in shifts if s['state'] != 'closed')}
