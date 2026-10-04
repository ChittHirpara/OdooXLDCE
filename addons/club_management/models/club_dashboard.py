from collections import defaultdict
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import email_normalize, html_escape

from .booking import club_today
from .club_support import FEEDBACK_AREAS

OPEN_HOURS_PER_DAY = 16     # courts open 06:00-22:00
SOURCES = [('membership', 'Memberships'), ('court', 'Court Bookings'),
           ('shop', 'Pro-Shop'), ('bar', 'Bar & Cafeteria')]
PERIODS = ('today', 'week', 'month', 'all')
PAYMENT_LABELS = {'cash': 'Cash', 'card': 'Card', 'upi': 'UPI', False: 'Paid at the club (method not recorded)'}
UTILIZATION_DAYS = 30
MAX_MONTHS = 24
PAYMENT_GRACE_DAYS = 3       # an unpaid club invoice older than this counts as a failed payment
CANCELLED_WINDOW_DAYS = 7
STALE_SHIFT_HOURS = 24
LOW_RATING = 2
DEFAULT_REMINDER_DAYS = 14


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
    def _money(self, date_from=None, date_to=None):
        """What the club owes and collects in tax, business-client billing, payroll and leave."""
        env = self.sudo().env
        finance = env['club.finance']
        today = club_today()
        tax = finance.tax_collected(date_from, date_to)['amount']
        owed = finance.payables()
        invoices = env['account.move'].search([
            ('move_type', 'in', ('out_invoice', 'out_refund')), ('state', '=', 'posted'),
            ('partner_id.is_company', '=', True)])
        if date_from:
            invoices = invoices.filtered(lambda m: date_from <= m.invoice_date <= (date_to or today))
        business_open = invoices.filtered(lambda m: m.payment_state in ('not_paid', 'partial'))
        run = env['club.payroll.run'].search([('month', '=', today.replace(day=1))], limit=1)
        pending_leave = env['hr.leave'].search_count([('state', 'in', ('confirm', 'validate1'))])
        return {
            'tax_collected': tax,
            'tax_label': "GST included in sales",
            'owed_bills': owed['bills'],
            'owed_salaries': owed['salaries'],
            'owed_total': owed['bills'] + owed['salaries'],
            'owed_count': owed['count'],
            'business_billed': sum(invoices.mapped('amount_total_signed')),
            'business_open': sum(business_open.mapped('amount_residual')),
            'business_clients': len(invoices.partner_id),
            'payroll_total': run.total if run else 0.0,
            'payroll_state': dict(run._fields['state'].selection).get(run.state) if run else 'Not started',
            'employees': env['hr.employee'].search_count([]),
            'pending_leave': pending_leave,
        }

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
            'open_tickets': env['club.ticket'].search_count([('state', 'in', ('new', 'progress'))]),
            'ratings': env['club.feedback'].rating_summary(),
            'money': self._money(date_from, date_to),
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
            tax = env['club.finance'].tax_collected(begin, min(month_end(begin), today))['amount']
            monthly.append({'month': begin.strftime('%b %Y'), 'total': total_all(rev), 'tax': tax, **rev})

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

    # ------------------------------------------------------------------
    # club home (the landing page for everyone on the team)
    # ------------------------------------------------------------------
    @api.model
    def get_home(self):
        """Numbers for the Club Home page. Open to all club staff: counts only, no revenue."""
        if not self.env.user.has_group('club_management.group_club_staff'):
            raise AccessError("Only club staff can open the club home page.")
        env = self.sudo().env
        today = club_today()
        low_stock = len(self._low_stock_points())
        days = int(env['ir.config_parameter'].get_param('club_management.reminder_days', DEFAULT_REMINDER_DAYS))
        return {
            'user': self.env.user.name,
            'is_manager': self.env.user.has_group('club_management.group_club_manager'),
            'today': today.strftime('%A %d %B %Y'),
            'counts': {
                'bookings_today': env['club.booking'].search_count([
                    ('booking_date', '=', today), ('state', '!=', 'cancelled')]),
                'open_enquiries': env['crm.lead'].search_count([
                    ('enquiry_ref', '!=', False), ('active', '=', True), ('probability', '<', 100)]),
                'open_tickets': env['club.ticket'].search_count([('state', 'in', ('new', 'progress'))]),
                'low_stock': low_stock,
                'pending_leave': env['hr.leave'].search_count([('state', 'in', ('confirm', 'validate1'))]),
                'expiring': env['res.partner'].search_count([
                    ('is_member', '=', True), ('member_state', '=', 'active'),
                    ('expiry_date', '>=', today), ('expiry_date', '<=', today + timedelta(days=days))]),
            },
        }

    # ------------------------------------------------------------------
    # system monitoring
    # ------------------------------------------------------------------
    @api.model
    def get_monitoring(self):
        """Health checks for the club's operation. Each check has a status (ok, warn or alert),
        a count and the first few offending records, so a manager sees what to act on."""
        self._require_manager("system monitoring")
        env = self.sudo().env
        today = club_today()
        now = fields.Datetime.now()
        symbol = self._currency_symbol()
        limit = 8
        checks = []

        def add(key, label, records, row, action, alert=False, hint=''):
            count = len(records)
            checks.append({
                'key': key, 'label': label, 'count': count, 'hint': hint, 'action': action,
                'status': 'ok' if not count else ('alert' if alert else 'warn'),
                'items': [row(record) for record in records[:limit]]})

        invoices = env['account.move'].search([
            ('move_type', '=', 'out_invoice'), ('state', '=', 'posted'), ('club_source', '!=', False),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('invoice_date', '<=', today - timedelta(days=PAYMENT_GRACE_DAYS))], order='invoice_date')
        add('failed_payments', 'Failed payments', invoices,
            lambda m: {'title': m.name, 'subtitle': m.partner_id.name or '',
                       'extra': '%s%s unpaid since %s' % (symbol, round(m.amount_residual), m.invoice_date)},
            'account.action_move_out_invoice_type', alert=True,
            hint="Club invoices still unpaid after %d days." % PAYMENT_GRACE_DAYS)

        since = fields.Datetime.subtract(now, days=CANCELLED_WINDOW_DAYS)
        cancelled = env['club.booking'].search([
            ('state', '=', 'cancelled'), ('write_date', '>=', since)], order='write_date desc')
        add('failed_bookings', 'Failed bookings', cancelled,
            lambda b: {'title': b.name,
                       'subtitle': '%s, %s' % (b.court_id.name, b.partner_id.name or b.walkin_name or 'Guest'),
                       'extra': 'cancelled'},
            'club_management.action_club_booking',
            hint="Bookings cancelled in the last %d days." % CANCELLED_WINDOW_DAYS)

        points = env['stock.warehouse.orderpoint'].search([]).filtered(
            lambda op: op.product_id.qty_available < op.product_min_qty)
        add('low_inventory', 'Low inventory', points,
            lambda op: {'title': op.product_id.name, 'subtitle': '%d on hand' % op.product_id.qty_available,
                        'extra': 'minimum %d' % op.product_min_qty},
            'stock.action_orderpoint', hint="Products below their reorder minimum.")

        days = int(env['ir.config_parameter'].get_param('club_management.reminder_days', DEFAULT_REMINDER_DAYS))
        expiring = env['res.partner'].search([
            ('is_member', '=', True), ('member_state', '=', 'active'),
            ('expiry_date', '>=', today), ('expiry_date', '<=', today + timedelta(days=days))], order='expiry_date')
        add('expiring_memberships', 'Expiring memberships', expiring,
            lambda p: {'title': p.name, 'subtitle': '%s, %s' % (p.member_id, p.plan_id.name),
                       'extra': 'ends %s' % p.expiry_date},
            'club_management.action_club_members', hint="Active memberships ending within %d days." % days)

        stale_before = fields.Datetime.subtract(now, hours=STALE_SHIFT_HOURS)
        sessions = env['pos.session'].search([
            '|', ('state', '=', 'closing_control'),
            '&', ('state', '!=', 'closed'), ('start_at', '<=', stale_before)], order='start_at')
        add('pos_sessions', 'POS / session issues', sessions,
            lambda s: {'title': s.name, 'subtitle': s.user_id.name,
                       'extra': '%s since %s' % (s.state.replace('_', ' '), s.start_at)},
            'point_of_sale.action_pos_session', alert=True,
            hint="Shifts open for more than %d hours, or stuck while closing." % STALE_SHIFT_HOURS)

        tickets = env['club.ticket'].search([('state', 'in', ('new', 'progress'))], order='priority desc, id')
        add('open_tickets', 'Open support tickets', tickets,
            lambda t: {'title': t.name, 'subtitle': t.subject, 'extra': '%d days old' % t.age_days},
            'club_management.action_club_tickets', hint="Requests that still need a reply or a fix.")

        bad = env['club.feedback'].search([('rating', '<=', LOW_RATING), ('reviewed', '=', False)], order='id desc')
        add('low_ratings', 'Unreviewed low ratings', bad,
            lambda f: {'title': '%s, %d stars' % (dict(FEEDBACK_AREAS)[f.area], f.rating),
                       'subtitle': f.name or 'Anonymous', 'extra': (f.comment or '')[:60]},
            'club_management.action_club_feedback',
            hint="Ratings of %d stars or less that nobody has read yet." % LOW_RATING)

        statuses = [c['status'] for c in checks]
        return {
            'checked_at': fields.Datetime.to_string(now),
            'overall': 'alert' if 'alert' in statuses else ('warn' if 'warn' in statuses else 'ok'),
            'checks': checks,
        }

    @api.model
    def _low_stock_points(self):
        return self.sudo().env['stock.warehouse.orderpoint'].search([]).filtered(
            lambda op: op.product_id.qty_available < op.product_min_qty)

    @api.model
    def _cron_low_stock_alert(self):
        """Daily: tell the managers which products are below their reorder minimum (nothing if none)."""
        points = self._low_stock_points()
        if not points:
            return 0
        managers = self.env.ref('club_management.group_club_manager').sudo().users.filtered(
            lambda u: u.active and u.email and not u.share)
        if not managers:
            return 0
        rows = ''.join('<tr><td>%s</td><td>%d on hand</td><td>minimum %d</td></tr>' % (
            html_escape(op.product_id.name), op.product_id.qty_available, op.product_min_qty) for op in points)
        self.env['mail.mail'].sudo().create({
            'subject': 'Low stock: %d product(s) need reordering' % len(points),
            'email_to': ','.join(managers.mapped('email')),
            'body_html': '<p>These products are below their reorder minimum:</p>'
                         '<table cellpadding="4">%s</table><p>The Champions Club</p>' % rows,
            'auto_delete': True,
        }).send()
        return len(points)

    # ------------------------------------------------------------------
    # sharing the numbers
    # ------------------------------------------------------------------
    @api.model
    def report_rows(self, period='month'):
        """The dashboard as (section, measure, value) rows: one source for the CSV and the e-mail."""
        data = self.get_dashboard_data(period)
        money = data['money']
        symbol = data['currency_symbol']

        def fmt(amount):
            return '%s%s' % (symbol, '{:,.0f}'.format(amount or 0))

        rows = [('Revenue', 'Total', fmt(data['total_revenue']))]
        rows += [('Revenue', item['label'], '%s (%s%%)' % (fmt(item['amount']), item['share']))
                 for item in data['by_source']]
        rows += [
            ('Members', 'Active members', data['active_members']),
            ('Members', 'Expired memberships', data['expired_members']),
            ('Courts', 'Bookings', data['court_bookings']),
            ('Courts', 'Utilization', '%s%%' % data['court_utilization']),
            ('Owed', 'Supplier bills unpaid', fmt(money['owed_bills'])),
            ('Owed', 'Salaries unpaid', fmt(money['owed_salaries'])),
            ('Owed', 'Total we owe', fmt(money['owed_total'])),
            ('Receivable', 'Unpaid customer invoices', fmt(data['outstanding_amount'])),
            ('Tax', 'GST included in sales', fmt(money['tax_collected'])),
            ('Business clients', 'Billed', fmt(money['business_billed'])),
            ('Business clients', 'Unpaid', fmt(money['business_open'])),
            ('People', 'Payroll this month', fmt(money['payroll_total'])),
            ('People', 'Leave waiting for approval', money['pending_leave']),
        ]
        return [(section, measure, str(value)) for section, measure, value in rows]

    @api.model
    def email_report(self, period='month', to=None):
        """E-mail the dashboard numbers (default: to yourself). Managers only. Returns the address used."""
        self._require_manager("the owner dashboard")
        address = email_normalize(to) if (to or '').strip() else email_normalize(self.env.user.email or '')
        if not address:
            raise UserError("Enter a valid e-mail address to send the report to.")
        period = period if period in PERIODS else 'month'
        rows = self.report_rows(period)
        body = ''.join('<tr><td>%s</td><td>%s</td><td style="text-align:right"><b>%s</b></td></tr>' % (
            html_escape(a), html_escape(b), html_escape(c)) for a, b, c in rows)
        self.env['mail.mail'].sudo().create({
            'subject': "The Champions Club: numbers (%s)" % dict(
                today='today', week='this week', month='this month', all='all time')[period],
            'email_to': address,
            'body_html': '<p>Here are the club numbers you asked for.</p>'
                         '<table cellpadding="6" style="border-collapse:collapse">%s</table>'
                         '<p>The Champions Club</p>' % body,
            'auto_delete': True,
        }).send()
        return address
