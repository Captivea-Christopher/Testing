{
    # App information
    'name': 'Shopify Extended',
    'version': '11.0',
    'license': 'OPL-1',
    'category': 'Sales',
    'summary': 'Shopify Extended will add the ability to create unregistered taxes with their set rates.  It also '
               'adds several fields, and the ability to set each orders salesperson.',

    # Author
    'author': 'Emipro Technologies (Customization)',
    'website': 'http://www.emiprotechnologies.com/',
    'maintainer': 'Emipro Technologies Pvt. Ltd.',

    # Dependencies
    'depends': ['shopify_ept'],

    # Views
    'init_xml': [],
    'data': [
        'security/ir.model.access.csv',
        'view/shopify_instance_ept_view.xml',
        'view/sale_order.xml',
        'view/res_users.xml',
        'wizard/shopify_refund_wizard_view.xml',
        'view/sale_workflow_extended_ept.xml',
    ],
    'demo_xml': [],

    'installable': True,
    'auto_install': False,
    'application': True,
}
