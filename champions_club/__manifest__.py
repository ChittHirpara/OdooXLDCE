# -*- coding: utf-8 -*-
{
    'name': 'Champions Club — Sports Club Management',
    'version': '19.0.1.0.0',
    'category': 'Sports & Recreation',
    'summary': 'Unified platform for Tennis, Padel & Badminton: Membership, Court Booking, POS, and Pro-Shop',
    'description': """
Champions Club — Sports Club Management System
===============================================
A modern, unified sports club operating system built for Odoo 19.
Features:
- Multi-tier Membership Plans (Junior, Silver, Gold VIP)
- Court booking engine for Tennis, Padel, and Badminton with live visual grid
- Pro-Shop & equipment eCommerce with live Odoo Inventory & member tier discounts
- Clubhouse Cafeteria / Sports Bar POS
- Member CRM & accounting analytics
    """,
    'author': 'Champions Club Hackathon Team',
    'website': 'https://github.com/ChittHirpara/OdooXLDCE',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/membership_demo_data.xml',
        'views/membership_menus.xml',
        'views/membership_plan_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'champions_club/static/src/scss/champions_variables.scss',
            'champions_club/static/src/components/membership_plans/membership_plans.scss',
            'champions_club/static/src/components/membership_plans/membership_plans.xml',
            'champions_club/static/src/components/membership_plans/membership_plans.js',
            'champions_club/static/src/components/court_booking/court_booking.scss',
            'champions_club/static/src/components/court_booking/court_booking.xml',
            'champions_club/static/src/components/court_booking/court_booking.js',
            'champions_club/static/src/components/shop/shop.scss',
            'champions_club/static/src/components/shop/shop.xml',
            'champions_club/static/src/components/shop/shop.js',
            'champions_club/static/src/components/bar_pos/bar_pos.scss',
            'champions_club/static/src/components/bar_pos/bar_pos.xml',
            'champions_club/static/src/components/bar_pos/bar_pos.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
