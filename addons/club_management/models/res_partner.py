import base64
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize

from .booking import club_today

JUNIOR_AGE_LIMIT = 18
DEFAULT_REMINDER_DAYS = 14


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_member = fields.Boolean(string='Club Member')
    plan_id = fields.Many2one('club.membership.plan', string='Membership Plan')
    member_id = fields.Char(string='Member ID', copy=False, readonly=True)
    date_of_birth = fields.Date()
    join_date = fields.Date(copy=False)
    expiry_date = fields.Date(copy=False)
    expiry_reminder_for = fields.Date(
        copy=False, readonly=True,
        help="Expiry date for which the reminder email was already sent.")
    qr_code = fields.Binary(compute='_compute_qr_code', string='Membership QR Code')
    is_junior = fields.Boolean(compute='_compute_is_junior')
    member_state = fields.Selection(
        [('none', 'Not a Member'), ('active', 'Active'), ('expired', 'Expired')],
        compute='_compute_member_state', store=True, default='none')

    _sql_constraints = [
        ('member_id_unique', 'unique(member_id)', 'Member ID must be unique.'),
    ]

    @api.depends('member_id')
    def _compute_qr_code(self):
        """QR image of the member ID, for the membership card and front-desk scanning."""
        Report = self.env['ir.actions.report']
        for partner in self:
            partner.qr_code = partner.member_id and base64.b64encode(
                Report.barcode('QR', partner.member_id, width=256, height=256))

    @api.depends('date_of_birth')
    def _compute_is_junior(self):
        today = club_today()
        for partner in self:
            dob = partner.date_of_birth
            partner.is_junior = bool(dob) and self._age_on(dob, today) < JUNIOR_AGE_LIMIT

    @api.depends('is_member', 'expiry_date')
    def _compute_member_state(self):
        today = club_today()
        for partner in self:
            if not partner.is_member or not partner.expiry_date:
                partner.member_state = 'none'
            elif partner.expiry_date >= today:
                partner.member_state = 'active'
            else:
                partner.member_state = 'expired'

    @staticmethod
    def _age_on(dob, day):
        return day.year - dob.year - ((day.month, day.day) < (dob.month, dob.day))

    @api.constrains('plan_id', 'date_of_birth', 'is_member')
    def _check_junior_plan(self):
        for partner in self.filtered(lambda p: p.is_member and p.plan_id.code == 'junior'):
            if not partner.date_of_birth:
                raise ValidationError("Junior members need a date of birth.")
            if not partner.is_junior:
                raise ValidationError(
                    "%s is %s or older and cannot hold a Junior membership."
                    % (partner.name, JUNIOR_AGE_LIMIT))

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._assign_member_id()
        partners.filtered('is_member')._sync_club_pricelist()
        return partners

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_member'):
            self._assign_member_id()
        if vals.keys() & {'is_member', 'plan_id', 'expiry_date'}:
            self._sync_club_pricelist()
        return res

    def _sync_club_pricelist(self):
        """Active members get their tier pricelist (used by POS and the website
        shop). When a membership ends, only a tier pricelist is removed: any
        pricelist set by hand is left alone."""
        club = self.env['club.membership.plan'].sudo().with_context(
            active_test=False).search([]).pricelist_id
        for partner in self:
            current = partner.sudo().property_product_pricelist
            plan = partner.plan_id
            if partner.is_member and partner.member_state == 'active' and plan.pricelist_id:
                if current != plan.pricelist_id:
                    partner.sudo().property_product_pricelist = plan.pricelist_id
            elif current in club:
                # Writing False would not reset the property, so drop it explicitly.
                self.env['ir.property'].sudo().search([
                    ('fields_id.name', '=', 'property_product_pricelist'),
                    ('fields_id.model', '=', 'res.partner'),
                    ('res_id', '=', 'res.partner,%s' % partner.id),
                ]).unlink()

    def _assign_member_id(self):
        for partner in self.filtered(lambda p: p.is_member and not p.member_id):
            partner.member_id = self.env['ir.sequence'].next_by_code('club.member')

    # ------------------------------------------------------------------
    # Scheduled actions
    # ------------------------------------------------------------------
    @api.model
    def _cron_lapse_memberships(self):
        """Mark members whose expiry date has passed as expired.

        member_state is stored and only depends on expiry_date, so nothing
        recomputes it when the date merely goes by: this job does.
        """
        stale = self.search([
            ('is_member', '=', True),
            ('member_state', '=', 'active'),
            ('expiry_date', '<', club_today()),
        ])
        if not stale:
            return 0
        self.env.add_to_compute(self._fields['member_state'], stale)
        stale._sync_club_pricelist()    # reads member_state, which triggers the recompute
        for partner in stale:
            partner.message_post(
                body="Club membership expired on %s." % partner.expiry_date,
                subtype_xmlid='mail.mt_note')
        return len(stale)

    @api.model
    def _cron_send_expiry_reminders(self):
        """Email active members whose membership ends within the reminder window.

        One email per expiry date: renewing moves the date, which re-arms the reminder.
        The window comes from the system parameter ``club_management.reminder_days``.
        """
        days = int(self.env['ir.config_parameter'].sudo().get_param(
            'club_management.reminder_days', DEFAULT_REMINDER_DAYS))
        today = club_today()
        template = self.env.ref('club_management.mail_template_membership_expiry')
        due = self.search([
            ('is_member', '=', True),
            ('member_state', '=', 'active'),
            ('expiry_date', '>=', today),
            ('expiry_date', '<=', today + timedelta(days=days)),
            ('email', '!=', False),
        ]).filtered(lambda p: p.expiry_reminder_for != p.expiry_date)
        for partner in due:
            template.send_mail(partner.id)
            partner.expiry_reminder_for = partner.expiry_date
        return len(due)

    def action_activate_membership(self):
        today = club_today()
        for partner in self:
            if not partner.plan_id:
                raise ValidationError("Select a membership plan for %s first." % partner.name)
            partner.write({
                'is_member': True,
                'join_date': partner.join_date or today,
                'expiry_date': today + timedelta(days=partner.plan_id.validity_days),
            })

    @api.model
    def _club_verify_member(self, member_ref, email):
        """The member for an online booking or order: the member ID plus the e-mail on file.

        The same message is given for every failure, so it cannot be used to find out
        which member IDs exist. A lapsed member still verifies (they pay full price).
        """
        ref = (member_ref or '').strip().upper()
        wanted = email_normalize((email or '').strip())
        partner = self.sudo().search([('member_id', '=', ref), ('is_member', '=', True)], limit=1) if ref else None
        if not partner or not wanted or email_normalize(partner.email or '') != wanted:
            raise ValidationError("We could not verify that member ID and e-mail address. "
                                  "Check them, or continue as a guest.")
        return partner

    def _get_active_plan(self, on=None):
        """The membership plan in force on ``on`` (club today by default), else an empty recordset.

        Single rule used by court pricing, shop, bar and the frontend: a member whose
        membership has ended gets no tier benefits.
        """
        self.ensure_one()
        on = on or club_today()
        if self.is_member and self.plan_id and self.expiry_date and self.expiry_date >= on:
            return self.plan_id
        return self.env['club.membership.plan']

    @api.model
    def get_current_member(self):
        """Return the current user's member profile or default active demo member."""
        user = self.env.user
        partner = user.partner_id
        if not partner.is_member:
            partner = self.search([('is_member', '=', True), ('member_state', '=', 'active')],
                                  order='id', limit=1) or user.partner_id
        plan = partner._get_active_plan()    # lapsed members get no tier benefits
        return {
            'id': partner.id,
            'name': partner.name,
            'member_id': partner.member_id or "CC-00001",
            'email': partner.email or "",
            'phone': partner.phone or "",
            'plan': plan.name if plan else "Guest",
            'plan_code': plan.code if plan else "none",
            'status': partner.member_state,
            'is_junior': partner.is_junior,
            'shop_discount': plan.shop_discount if plan else 0.0,
            'bar_discount': plan.bar_discount if plan else 0.0,
            'court_rate': plan.court_rate if plan else 0.0,
            'expiry_date': partner.expiry_date.isoformat() if partner.expiry_date else None,
        }

    @api.model
    def get_members_list(self):
        """Return all members for POS, Booking and Shop selectors."""
        members = self.search([('is_member', '=', True)], order='name asc')
        result = []
        for m in members:
            plan = m._get_active_plan()    # lapsed members get no tier benefits
            result.append({
                'id': m.id,
                'name': m.name,
                'member_id': m.member_id or f"CC-{m.id:04d}",
                'plan': plan.name if plan else "Guest",
                'plan_code': plan.code if plan else "none",
                'planCode': plan.code if plan else "none",
                'status': m.member_state,
                'is_active': m.member_state == 'active',
                'discountPct': plan.bar_discount if plan else 0.0,
                'shopDiscountPct': plan.shop_discount if plan else 0.0,
                'expiry_date': m.expiry_date.isoformat() if m.expiry_date else None,
            })
        # Always include walk-in guest option
        result.append({
            'id': 0,
            'name': "Walk-in Guest",
            'member_id': "GUEST-001",
            'plan': "Guest",
            'plan_code': "none",
            'planCode': "none",
            'status': "none",
            'is_active': True,
            'discountPct': 0,
            'shopDiscountPct': 0,
            'expiry_date': None,
        })
        return result

    @api.model
    def register_or_renew_member(self, partner_id, plan_code):
        """Register or renew a club membership for a partner."""
        partner = self.browse(partner_id)
        if not partner.exists():
            raise ValidationError("Partner not found.")
        plan = self.env['club.membership.plan'].search([('code', '=', plan_code)], limit=1)
        if not plan:
            raise ValidationError(f"Unknown membership tier: {plan_code}")
        partner.plan_id = plan.id
        partner.action_activate_membership()
        return partner.get_current_member()
