from odoo import models, fields, api, _


class ResUsers(models.Model):
    _inherit = "res.users"

    shopify_instance_ids = fields.One2many('shopify.salesperson.instance.ept', 'user_id', string="Shopify Instance Salesperson")