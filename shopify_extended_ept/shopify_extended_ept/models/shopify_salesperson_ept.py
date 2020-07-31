from odoo import models, fields, api, _

class ShopifySalespersonInstanceEPT(models.Model):
    _name = "shopify.salesperson.instance.ept"

    user_id = fields.Many2one('res.users', string="Customer")
    shopify_user_id = fields.Char(string="User Id")
    instance_id = fields.Many2one('shopify.instance.ept',string="Instance")