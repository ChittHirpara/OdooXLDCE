from datetime import timedelta

from odoo.addons.club_management.models.booking import club_today
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'club_management')
class TestMember(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gold = cls.env.ref('club_management.plan_gold')
        cls.junior = cls.env.ref('club_management.plan_junior')
        cls.today = club_today()

    def test_activate_sets_dates_and_member_id(self):
        partner = self.env['res.partner'].create({'name': 'Gold Guy', 'plan_id': self.gold.id})
        partner.action_activate_membership()
        self.assertTrue(partner.is_member)
        self.assertTrue(partner.member_id.startswith('CC-'))
        self.assertEqual(partner.expiry_date, self.today + timedelta(days=self.gold.validity_days))
        self.assertEqual(partner.member_state, 'active')

    def test_expired_state(self):
        partner = self.env['res.partner'].create({
            'name': 'Old Member', 'is_member': True, 'plan_id': self.gold.id,
            'expiry_date': self.today - timedelta(days=1)})
        self.assertEqual(partner.member_state, 'expired')

    def test_non_member_state(self):
        partner = self.env['res.partner'].create({'name': 'Visitor'})
        self.assertEqual(partner.member_state, 'none')
        self.assertFalse(partner.member_id)

    def test_junior_must_be_under_18(self):
        adult_dob = self.today - timedelta(days=365 * 30)
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': 'Too Old', 'is_member': True, 'plan_id': self.junior.id,
                'date_of_birth': adult_dob})

    def test_junior_requires_dob(self):
        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': 'No DOB', 'is_member': True, 'plan_id': self.junior.id})

    def test_junior_valid(self):
        kid = self.env['res.partner'].create({
            'name': 'Kid', 'is_member': True, 'plan_id': self.junior.id,
            'date_of_birth': self.today - timedelta(days=365 * 10)})
        self.assertTrue(kid.is_junior)
