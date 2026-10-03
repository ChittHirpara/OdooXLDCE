{
    'name': 'Club Website',
    'version': '17.0.1.0.0',
    'category': 'Website',
    'summary': 'Public website for The Champions Club: membership, courts, shop and the join enquiry',
    'description': """
Public pages that sit on top of Club Management. They add no data of their own:
plans, courts, products and stock come from Club Management, and every enquiry
becomes a CRM lead there.
    """,
    'author': 'Hackathon Team',
    'license': 'LGPL-3',
    'depends': ['website', 'club_management'],
    'data': [
        'views/layout_templates.xml',
        'views/home_templates.xml',
        'views/membership_templates.xml',
        'views/court_templates.xml',
        'views/shop_templates.xml',
        'views/join_templates.xml',
        'views/page_templates.xml',
        'data/website_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'club_website/static/src/scss/club_website.scss',
            'club_website/static/src/js/availability.js',
        ],
    },
    'post_init_hook': 'post_init',
    'installable': True,
    'application': False,
}
