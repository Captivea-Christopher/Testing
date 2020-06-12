# coding: utf-8
# Part of CAPTIVEA. Odoo 12 EE.

{
    'name': "cap_account_reconciliation",
    'version': "12.0",
    'author': "captivea-jpa",
    'summary': "Manage the 'account' reconciliation view.",
    'depends': ["account"],
    'data': ["views/assets_backend.xml"],
    'qweb': ["static/src/xml/account_reconciliation_widget.xml"],
    'installable': True
}
