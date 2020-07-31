from odoo import models, fields

class ShopifyCustomerDetailEPT(models.Model):
    _name = "shopify.customer.details.ept"

    partner_id = fields.Many2one('res.partner', string="Customer")
    shopify_customer_id = fields.Char(string="Customer Id")
    instance_id = fields.Many2one('shopify.instance.ept',string="Instance")