from odoo import models,api,fields

class res_partner(models.Model) :
    _inherit = 'res.partner'

    shopify_instance_id = fields.Many2one('shopify.instance.ept',string="Shopify Instance")
