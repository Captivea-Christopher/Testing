# -*- coding: utf-8 -*-
{
    'name': "cap_portal_task_submission",

    'summary': """
        Adds customer task submission page
        """,

    'description': """
        Adds a new webpage which allows a customer to submit a task directly to a project.
        Adds a button to the user portal that redirects to the page where tasks are submitted.
    """,

    'author': "Christopher Beirne Captivea",
    'website': "https://www.Captivea.us/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','website','project','contacts'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/templates.xml',
    ]
}