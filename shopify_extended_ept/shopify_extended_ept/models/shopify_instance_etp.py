from odoo import models, fields, api, _
from odoo.addons.shopify_ept import shopify
from odoo.exceptions import Warning

class ShopifyInstanceEPT(models.Model):
    _inherit = "shopify.instance.ept"

    account_id = fields.Many2one('account.account', string='Tax Account', ondelete='restrict',
                                 help="Account that will be set on invoice tax lines for invoices. Leave empty to use the expense account.")
    refund_account_id = fields.Many2one('account.account', string='Tax Account on Credit Notes', ondelete='restrict',
                                        help="Account that will be set on invoice tax lines for credit notes. Leave empty to use the expense account.")
    default_auto_workflow_id = fields.Many2one("sale.workflow.process.ept", "Defult Auto Workflow")
    shopify_salesperson_id = fields.Many2one('res.users', string='Salesperson',help="Here if you selected the saleperson it will add in order in Salesperson, otherwise it will take current user as salesperson while import orders from shopify ==> Odoo")
    # shopify_store_time_zone = fields.Char("Store Time Zone",
    #                                       help='This field used to import order process')

    def test_shopify_connection(self):
        shop = self.host.split("//")
        if len(shop) == 2:
            shop_url = shop[0] + "//" + self.api_key + ":" + self.password + "@" + shop[
                1] + "/admin"
        else:
            shop_url = "https://" + self.api_key + ":" + self.password + "@" + shop[0] + "/admin"
        shopify.ShopifyResource.set_site(shop_url)
        try:
            shop_id = shopify.Shop.current()
            shop_detail = shop_id.to_dict()
            self.write({'shopify_store_time_zone': shop_detail.get('timezone')})
            self._cr.commit()
        except Exception as e:
            raise Warning(e)
        raise Warning('Service working properly')