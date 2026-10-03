from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

JUNIOR_AGE_LIMIT = 18


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_member = fields.Boolean(string='Club Member')
    plan_id = fields.Many2one('club.membership.plan', string='Membership Plan')
    member_id = fields.Char(string='Member ID', copy=False, readonly=True)
    date_of_birth = fields.Date()
    join_date = fields.Date(copy=False)
    expiry_date = fields.Date(copy=False)
    is_junior = fields.Boolean(compute='_compute_is_junior')
    member_state = fields.Selection(
        [('none', 'Not a Member'), ('active', 'Active'), ('expired', 'Expired')],
        compute='_compute_member_state', store=True, default='none')

    _sql_constraints = [
        ('member_id_unique', 'unique(member_id)', 'Member ID must be unique.'),
    ]

    @api.depends('date_of_birth')
    def _compute_is_junior(self):
        today = fields.Date.context_today(self)
        for partner in self:
            dob = partner.date_of_birth
            partner.is_junior = bool(dob) and self._age_on(dob, today) < JUNIOR_AGE_LIMIT

    @api.depends('is_member', 'expiry_date')
    def _compute_member_state(self):
        today = fields.Date.context_today(self)
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

    def action_activate_membership(self):
        today = fields.Date.context_today(self)
        for partner in self:
            if not partner.plan_id:
                raise ValidationError("Select a membership plan for %s first." % partner.name)
            partner.write({
                'is_member': True,
                'join_date': partner.join_date or today,
                'expiry_date': today + timedelta(days=partner.plan_id.validity_days),
            })
