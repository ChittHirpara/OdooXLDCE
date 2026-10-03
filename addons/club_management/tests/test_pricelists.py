from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'club_management')
class TestTierPricelists(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gold = cls.env.ref('club_management.plan_gold')
        cls.silver = cls.env.ref('club_management.plan_silver')
        cls.junior = cls.env.ref('club_management.plan_junior')
        Product = cls.env['product.product']
        cls.shop_item = Product.create({
            'name': 'Racket', 'list_price': 100.0,
            'categ_id': cls.env.ref('club_management.product_category_shop').id})
        cls.bar_item = Product.create({
            'name': 'Smoothie', 'list_price': 100.0,
            'categ_id': cls.env.ref('club_management.product_category_bar').id})
        cls.other_item = Product.create({'name': 'Misc', 'list_price': 100.0})
        cls.today = fields.Date.context_today(cls.env['res.partner'])

    def _price(self, plan, product):
        return plan.pricelist_id._get_product_price(product, 1.0)

    def _member(self, plan, name='Member', **extra):
        partner = self.env['res.partner'].create(dict(name=name, plan_id=plan.id, **extra))
        partner.action_activate_membership()
        return partner

    # --- pricelists generated from plans ------------------------------------
    def test_every_plan_has_a_pricelist(self):
        for plan in (self.gold, self.silver, self.junior):
            self.assertTrue(plan.pricelist_id)
        self.assertEqual(len({self.gold.pricelist_id, self.silver.pricelist_id,
                              self.junior.pricelist_id}), 3)

    def test_gold_discounts(self):
        self.assertEqual(self._price(self.gold, self.shop_item), 80.0)   # 20% shop
        self.assertEqual(self._price(self.gold, self.bar_item), 85.0)    # 15% bar

    def test_silver_discounts(self):
        self.assertEqual(self._price(self.silver, self.shop_item), 90.0)
        self.assertEqual(self._price(self.silver, self.bar_item), 90.0)

    def test_junior_has_shop_discount_only(self):
        self.assertEqual(self._price(self.junior, self.shop_item), 95.0)
        self.assertEqual(self._price(self.junior, self.bar_item), 100.0)

    def test_other_categories_not_discounted(self):
        for plan in (self.gold, self.silver, self.junior):
            self.assertEqual(self._price(plan, self.other_item), 100.0)

    def test_child_category_inherits_discount(self):
        child = self.env['product.category'].create({
            'name': 'Cold Drinks', 'parent_id': self.env.ref('club_management.product_category_bar').id})
        drink = self.env['product.product'].create({'name': 'Cola', 'list_price': 100.0, 'categ_id': child.id})
        self.assertEqual(self._price(self.gold, drink), 85.0)

    def test_changing_plan_discount_updates_pricelist(self):
        self.gold.bar_discount = 25.0
        self.assertEqual(self._price(self.gold, self.bar_item), 75.0)
        self.gold.bar_discount = 0.0
        self.assertEqual(self._price(self.gold, self.bar_item), 100.0)
        self.gold.bar_discount = 15.0

    def test_renaming_plan_renames_pricelist(self):
        self.junior.name = 'Junior Squad'
        self.assertEqual(self.junior.pricelist_id.name, 'Club Junior Squad')
        self.junior.name = 'Junior'

    def test_sync_recreates_missing_pricelist(self):
        old = self.junior.pricelist_id
        self.junior.pricelist_id = False
        self.junior._sync_pricelist()
        self.assertTrue(self.junior.pricelist_id)
        self.assertNotEqual(self.junior.pricelist_id, old)
        self.assertEqual(self._price(self.junior, self.shop_item), 95.0)

    # --- member -> pricelist ------------------------------------------------
    def test_active_member_gets_tier_pricelist(self):
        member = self._member(self.gold)
        self.assertEqual(member.property_product_pricelist, self.gold.pricelist_id)

    def test_non_member_keeps_default_pricelist(self):
        partner = self.env['res.partner'].create({'name': 'Visitor', 'plan_id': self.gold.id})
        club = (self.gold | self.silver | self.junior).pricelist_id
        self.assertNotIn(partner.property_product_pricelist, club)

    def test_changing_plan_switches_pricelist(self):
        member = self._member(self.gold)
        member.plan_id = self.silver
        self.assertEqual(member.property_product_pricelist, self.silver.pricelist_id)

    def test_expired_member_loses_tier_pricelist(self):
        member = self._member(self.silver)
        member.expiry_date = self.today - timedelta(days=1)
        club = (self.gold | self.silver | self.junior).pricelist_id
        self.assertNotIn(member.property_product_pricelist, club)

    def test_renewal_restores_tier_pricelist(self):
        member = self._member(self.silver)
        member.expiry_date = self.today - timedelta(days=1)
        member.action_activate_membership()
        self.assertEqual(member.property_product_pricelist, self.silver.pricelist_id)

    def test_manual_pricelist_not_removed_on_expiry(self):
        member = self._member(self.silver)
        vip = self.env['product.pricelist'].create({'name': 'VIP manual'})
        member.property_product_pricelist = vip
        member.expiry_date = self.today - timedelta(days=1)
        self.assertEqual(member.property_product_pricelist, vip)

    def test_member_pays_discounted_price_via_own_pricelist(self):
        member = self._member(self.gold)
        self.assertEqual(
            member.property_product_pricelist._get_product_price(self.bar_item, 1.0), 85.0)

    # --- POS ----------------------------------------------------------------
    def test_pos_configs_offer_tier_pricelists(self):
        config = self.env['pos.config'].search([], limit=1)
        if not config:
            self.skipTest("no POS config in this database")
        config._enable_club_pricelists()
        club = (self.gold | self.silver | self.junior).pricelist_id
        self.assertTrue(config.use_pricelist)
        self.assertLessEqual(club, config.available_pricelist_ids)
        if config.pricelist_id:
            self.assertIn(config.pricelist_id, config.available_pricelist_ids)

    def test_new_pos_config_gets_tier_pricelists(self):
        config = self.env['pos.config'].create({'name': 'Bar Counter'})
        club = (self.gold | self.silver | self.junior).pricelist_id
        self.assertTrue(config.use_pricelist)
        self.assertLessEqual(club, config.available_pricelist_ids)
