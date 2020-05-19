# -*- coding: utf-8 -*-
# Part of CAPTIVEA. Odoo 12 EE.

from odoo import models, fields, api

class my_module(models.Model):
    _inherit = 'res.partner'

    biography = fields.Text()    #no uppercase, gets changed by the system