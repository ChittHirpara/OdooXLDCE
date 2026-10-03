# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ClubCourt(models.Model):
    _name = 'club.court'
    _description = 'Sports Club Court'
    _order = 'sequence asc, name asc'

    name = fields.Char(string='Court Name', required=True) # e.g. "Court 1", "Court 2"
    court_type = fields.Selection([
        ('padel', 'Padel'),
        ('tennis', 'Tennis'),
        ('badminton', 'Badminton'),
    ], string='Sport Discipline', required=True, default='padel')

    surface = fields.Selection([
        ('clay', 'Red Clay'),
        ('hard', 'DecoTurf Hard Court'),
        ('grass', 'Grass Court'),
        ('synthetic', 'Synthetic Turf'),
        ('wooden', 'Sprung Hardwood'),
    ], string='Playing Surface', default='synthetic')

    is_indoor = fields.Boolean(string='Indoor / Covered', default=False)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    # Base pricing
    base_hourly_rate = fields.Monetary(string='Base Hourly Rate', currency_field='currency_id', default=800.0)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    booking_ids = fields.One2many('club.booking', 'court_id', string='Bookings')

    @api.model
    def get_courts_list(self):
        """Returns list of active courts for OWL CourtGrid."""
        courts = self.search([('active', '=', True)], order='sequence asc')
        return [
            {
                'id': c.id,
                'name': c.name,
                'court_type': c.court_type,
                'surface': dict(c._fields['surface'].selection).get(c.surface, ''),
                'is_indoor': c.is_indoor,
                'base_rate': float(c.base_hourly_rate),
                'currency': c.currency_id.symbol or '₹',
            }
            for c in courts
        ]
