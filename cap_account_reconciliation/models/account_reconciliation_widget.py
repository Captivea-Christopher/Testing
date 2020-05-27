# coding: utf-8
# Part of CAPTIVEA. Odoo 12 EE.

import re

from odoo import api, models


class AccountReconciliationWidget(models.AbstractModel):
    """Manage 'account.reconciliation.widget' model. Overriding model."""
    _inherit = "account.reconciliation.widget"

    @api.model
    def _domain_move_lines(self, search_str):
        """Returns the domain from the search_str search. Overriding method."""
        # CALL SUPER
        str_domain = super(AccountReconciliationWidget, self)._domain_move_lines(search_str=search_str)

#         ids = []
#         domain = [("full_reconcile_id", "=", False), ("balance", "!=", 0), ("account_id.reconcile", "=", True), ("x_channel_name", "ilike", search_str)]
        
#         for account_move_line_id in self.env['account.move.line'].search(domain):
#             ids.append(account_move_line_id.id)
        str_domain = ["|", ("x_channel_name", "ilike", search_str)] + str_domain

        
        return str_domain
