# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date, timedelta

class ChampionsMembershipContract(models.Model):
    _name = 'champions.membership.contract'
    _description = 'Champions Club Member Subscription Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin'] if 'mail.thread' in dir() else []
    _order = 'start_date desc'

    name = fields.Char(string='Membership ID', required=True, copy=False, readonly=True, default=lambda self: 'NEW-MBR')
    partner_id = fields.Many2one('res.partner', string='Member', required=True)
    member_name = fields.Char(related='partner_id.name', string='Member Name', readonly=True)
    member_email = fields.Char(related='partner_id.email', string='Email', readonly=True)
    member_phone = fields.Char(related='partner_id.phone', string='Phone', readonly=True)

    plan_id = fields.Many2one('champions.membership.plan', string='Membership Plan', required=True)
    billing_cycle = fields.Selection([
        ('monthly', 'Monthly Billing'),
        ('annual', 'Annual Billing'),
    ], string='Billing Cycle', default='monthly', required=True)

    primary_sport = fields.Selection([
        ('tennis', 'Tennis'),
        ('padel', 'Padel'),
        ('badminton', 'Badminton'),
        ('multi', 'Multi-Sport'),
    ], string='Primary Sport Interest', default='multi')

    start_date = fields.Date(string='Contract Start Date', default=fields.Date.context_today, required=True)
    end_date = fields.Date(string='Renewal / Expiry Date', compute='_compute_end_date', store=True)

    state = fields.Selection([
        ('draft', 'Draft / Pending Payment'),
        ('active', 'Active Member'),
        ('paused', 'Paused'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='active', tracking=True)

    fee_amount = fields.Monetary(string='Subscription Fee', currency_field='currency_id')
    currency_id = fields.Many2one(related='plan_id.currency_id', string='Currency', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'NEW-MBR') == 'NEW-MBR':
                vals['name'] = self.env['ir.sequence'].next_by_code('champions.membership.contract') or 'CC-MEM-%05d' % self.search_count([])
        return super().create(vals_list)

    @api.depends('start_date', 'billing_cycle')
    def _compute_end_date(self):
        for rec in self:
            if rec.start_date:
                if rec.billing_cycle == 'annual':
                    rec.end_date = rec.start_date + timedelta(days=365)
                else:
                    rec.end_date = rec.start_date + timedelta(days=30)
            else:
                rec.end_date = False
