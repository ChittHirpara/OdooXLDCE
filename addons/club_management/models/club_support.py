"""Customer support and feedback: tickets (complaints, booking and order issues, refund
requests) and star ratings of the court, bar, shop and club experience."""
import secrets

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize

FEEDBACK_AREAS = [
    ('court', 'Court experience'), ('bar', 'Bar & Cafeteria experience'),
    ('shop', 'Pro-Shop experience'), ('club', 'Overall club')]
TICKET_CATEGORIES = [
    ('complaint', 'Complaint'), ('booking', 'Booking issue'), ('refund', 'Refund request'),
    ('order', 'Shop or bar order issue'), ('other', 'Something else')]
TICKET_STATES = [('new', 'New'), ('progress', 'In progress'), ('resolved', 'Resolved'), ('closed', 'Closed')]
MAX_TEXT = 2000


def _clean(value, limit):
    return (value or '').strip()[:limit]


class ClubFeedback(models.Model):
    _name = 'club.feedback'
    _description = 'Club Feedback and Rating'
    _order = 'id desc'

    area = fields.Selection(FEEDBACK_AREAS, required=True, default='club')
    rating = fields.Integer(required=True, group_operator='avg', help="1 (poor) to 5 (excellent).")
    stars = fields.Char(compute='_compute_stars')
    comment = fields.Text()
    partner_id = fields.Many2one('res.partner', string='Member / Customer')
    name = fields.Char(string='Name')
    email = fields.Char()
    booking_id = fields.Many2one('club.booking', string='Booking')
    order_id = fields.Many2one('club.order', string='Order')
    source = fields.Selection([('website', 'Website'), ('staff', 'Front desk')], default='website')
    reviewed = fields.Boolean(help="Tick once someone on the team has read it.")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    _sql_constraints = [
        ('rating_range', 'CHECK(rating BETWEEN 1 AND 5)', 'The rating must be from 1 to 5 stars.'),
    ]

    @api.depends('rating')
    def _compute_stars(self):
        for feedback in self:
            feedback.stars = '★' * feedback.rating + '☆' * (5 - feedback.rating)

    @api.model
    def create_public(self, area, rating, comment=None, name=None, email=None, partner_id=None,
                      booking_token=None, order_token=None):
        """Store feedback from the website. Runs with elevated rights (visitors are anonymous)
        and raises ValidationError with a presentable message on bad input."""
        if area not in dict(FEEDBACK_AREAS):
            raise ValidationError("Please choose what you are rating.")
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            rating = 0
        if not 1 <= rating <= 5:
            raise ValidationError("Please choose a rating from 1 to 5 stars.")
        email = _clean(email, 120)
        if email and not email_normalize(email):
            raise ValidationError("The email address is not valid.")
        booking = self.env['club.booking'].get_by_token(booking_token) if booking_token else self.env['club.booking']
        order = self.env['club.order'].get_by_token(order_token) if order_token else self.env['club.order']
        partner = self.env['res.partner'].sudo().browse(int(partner_id or 0)).exists() or booking.partner_id or order.partner_id
        return self.sudo().create({
            'area': area, 'rating': rating, 'comment': _clean(comment, MAX_TEXT) or False,
            'partner_id': partner.id or False, 'name': _clean(name, 100) or partner.name or False,
            'email': email or partner.email or False, 'booking_id': booking.id or False,
            'order_id': order.id or False, 'source': 'website'})

    @api.model
    def rating_summary(self, days=None):
        """Average rating and count per area (and overall), for the dashboard."""
        domain = []
        if days:
            domain.append(('create_date', '>=', fields.Datetime.subtract(fields.Datetime.now(), days=days)))
        feedback = self.sudo().search(domain)
        rows = []
        for key, label in FEEDBACK_AREAS:
            part = feedback.filtered(lambda f: f.area == key)
            rows.append({'area': key, 'label': label, 'count': len(part),
                         'average': round(sum(part.mapped('rating')) / len(part), 2) if part else 0.0})
        return {'rows': rows, 'count': len(feedback),
                'average': round(sum(feedback.mapped('rating')) / len(feedback), 2) if feedback else 0.0}


class ClubTicket(models.Model):
    _name = 'club.ticket'
    _description = 'Club Support Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, id desc'

    name = fields.Char(string='Reference', default='New', copy=False, readonly=True)
    subject = fields.Char(required=True, tracking=True)
    category = fields.Selection(TICKET_CATEGORIES, required=True, default='complaint', tracking=True)
    description = fields.Text()
    state = fields.Selection(TICKET_STATES, default='new', required=True, tracking=True, copy=False)
    priority = fields.Selection([('0', 'Normal'), ('1', 'High'), ('2', 'Urgent')], default='0', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Member / Customer', tracking=True)
    contact_name = fields.Char()
    contact_email = fields.Char()
    contact_phone = fields.Char()
    booking_id = fields.Many2one('club.booking', string='Booking')
    order_id = fields.Many2one('club.order', string='Order')
    user_id = fields.Many2one('res.users', string='Assigned to', tracking=True,
                              domain=lambda self: [('groups_id', 'in', self.env.ref('club_management.group_club_staff').id)])
    refund_amount = fields.Monetary(tracking=True, help="Amount to refund, for a refund request.")
    resolution = fields.Text(help="What was done. Sent to the customer when the ticket is resolved.")
    access_token = fields.Char(copy=False, readonly=True, index=True)
    source = fields.Selection([('website', 'Website'), ('staff', 'Front desk')], default='staff')
    resolved_date = fields.Datetime(copy=False, readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    age_days = fields.Integer(compute='_compute_age_days', string='Age (days)')

    @api.depends('create_date', 'state', 'resolved_date')
    def _compute_age_days(self):
        now = fields.Datetime.now()
        for ticket in self:
            end = ticket.resolved_date if ticket.state in ('resolved', 'closed') and ticket.resolved_date else now
            ticket.age_days = (end - ticket.create_date).days if ticket.create_date else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('club.ticket') or 'New'
            vals.setdefault('access_token', secrets.token_urlsafe(24))
            if not vals.get('user_id'):
                vals['user_id'] = self.env['crm.lead']._club_default_assignee().id or False
        tickets = super().create(vals_list)
        for ticket in tickets:
            if ticket.user_id and ticket.user_id.id != SUPERUSER_ID:
                ticket.activity_schedule(
                    'mail.mail_activity_data_todo', summary="Support ticket %s" % ticket.name,
                    note=ticket.subject, user_id=ticket.user_id.id)
        return tickets

    # ------------------------------------------------------------------
    # workflow
    # ------------------------------------------------------------------
    def action_start(self):
        self.filtered(lambda t: t.state == 'new').write({'state': 'progress'})

    def action_resolve(self):
        for ticket in self.filtered(lambda t: t.state in ('new', 'progress')):
            ticket.write({'state': 'resolved', 'resolved_date': fields.Datetime.now()})
            ticket.activity_feedback(['mail.mail_activity_data_todo'])
            ticket._send_template('club_management.mail_template_ticket_resolved')

    def action_close(self):
        for ticket in self.filtered(lambda t: t.state != 'closed'):
            ticket.write({'state': 'closed', 'resolved_date': ticket.resolved_date or fields.Datetime.now()})

    def action_reopen(self):
        self.filtered(lambda t: t.state in ('resolved', 'closed')).write({'state': 'progress', 'resolved_date': False})

    def _send_template(self, xmlid):
        template = self.env.ref(xmlid, raise_if_not_found=False)
        for ticket in self:
            if template and (ticket.contact_email or ticket.partner_id.email):
                template.sudo().send_mail(ticket.id)

    # ------------------------------------------------------------------
    # public intake
    # ------------------------------------------------------------------
    @api.model
    def create_public(self, name, category, subject, description=None, email=None, phone=None,
                      partner_id=None, booking_token=None, order_token=None):
        """A support request from the website. Raises ValidationError with a presentable message."""
        name = _clean(name, 100)
        email = _clean(email, 120)
        phone = _clean(phone, 30)
        subject = _clean(subject, 150)
        if not name:
            raise ValidationError("Please tell us your name.")
        if not email and not phone:
            raise ValidationError("Please give an email address or a phone number so we can reply.")
        if email and not email_normalize(email):
            raise ValidationError("The email address is not valid.")
        if category not in dict(TICKET_CATEGORIES):
            raise ValidationError("Please choose what your request is about.")
        if not subject:
            raise ValidationError("Please give your request a short title.")
        booking = self.env['club.booking'].get_by_token(booking_token) if booking_token else self.env['club.booking']
        order = self.env['club.order'].get_by_token(order_token) if order_token else self.env['club.order']
        partner = self.env['res.partner'].sudo().browse(int(partner_id or 0)).exists() or booking.partner_id or order.partner_id
        ticket = self.sudo().with_context(mail_create_nolog=True).create({
            'subject': subject, 'category': category, 'description': _clean(description, MAX_TEXT) or False,
            'contact_name': name, 'contact_email': email or partner.email or False,
            'contact_phone': phone or False, 'partner_id': partner.id or False,
            'booking_id': booking.id or False, 'order_id': order.id or False,
            'priority': '1' if category == 'refund' else '0', 'source': 'website'})
        ticket._send_template('club_management.mail_template_ticket_received')
        return ticket

    def _public_status(self):
        """What a customer may see about their request: nothing internal."""
        self.ensure_one()
        return {
            'reference': self.name, 'subject': self.subject, 'category': dict(TICKET_CATEGORIES)[self.category],
            'state': dict(TICKET_STATES)[self.state], 'state_key': self.state,
            'resolution': self.resolution if self.state in ('resolved', 'closed') else False,
            'received': fields.Datetime.to_string(self.create_date),
        }

    def get_by_token(self, token):
        token = (token or '').strip()
        return self.sudo().search([('access_token', '=', token)], limit=1) if len(token) >= 16 else self.browse()
