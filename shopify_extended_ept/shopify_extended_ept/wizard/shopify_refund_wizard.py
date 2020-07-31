# coding: utf-8
import time

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.addons.shopify_ept import shopify
from odoo.addons.shopify_ept.shopify.pyactiveresource.util import xml_to_dict


class ShopifyRefundWizard(models.TransientModel):
    _inherit = "shopify.cancel.refund.order.wizard"

    restock_type = fields.Selection([('no_restock', 'No Return'), ('cancel', 'Cancel'), ('return', 'Return')
                                     ], string="Restock Type", default='no_restock',
                                    help="No Return: Refunding these items won't affect inventory.\n"
                                         "Cancel: The items have not yet been fulfilled. The canceled quantity will be added back to the available count. The number of fulfillable units for this line item will decrease.\n"
                                         "Return: The items were already delivered but will be returned to the merchant. The returned quantity will be added back to the available count. The number of fulfillable units for this line item will remain unchanged.\n")

    def refund_in_shopify(self):
        """
        Use: Override this refund in shopify method to take changes based on new shopifu refund api.
        Added by: Jay Makwana @Emipro Technologies
        Added on: 25/2/20
        :return:
        """
        refund_invoice_id = self._context.get('id') or self._context.get('active_id')
        refunds = self.env['account.invoice'].browse(refund_invoice_id)
        transaction_log_obj = self.env["shopify.transaction.log"]

        restock_type = self.restock_type
        not_process = False
        orders = []
        for refund in refunds:
            if not refund.shopify_instance_id:
                continue
            refund.shopify_instance_id.connect_in_shopify()
            notify = self.notify_by_email
            if refund.source_invoice_id:
                lines = self.env['sale.order.line'].search(
                    [('invoice_lines.invoice_id', '=', refund.source_invoice_id.id)])
                order_ids = [line.order_id.id for line in lines]
                orders = order_ids and self.env['sale.order'].browse(list(set(order_ids))) or []

            elif refund.picking_id:
                for move in refund.picking_id.move_lines:
                    if move.sale_line_id:
                        orders = move.sale_line_id.order_id
                        break
            refund_lines_list = []
            note = ''
            for invoice_line_id in refund.refund_invoice_id.invoice_line_ids:
                for refund_invoice_line in refund.invoice_line_ids:
                    if invoice_line_id.product_id.id == refund_invoice_line.product_id.id:
                        if invoice_line_id.product_id.type == 'service':
                            continue
                        else:
                            shopify_line_id = invoice_line_id.mapped('sale_line_ids').shopify_line_id
                            refund_lines_dict = {'line_item_id': shopify_line_id,
                                                 'quantity': int(refund_invoice_line.quantity),
                                                 'restock_type': restock_type}
                            if restock_type == 'cancel' or restock_type == 'return':
                                order_id = invoice_line_id.mapped('sale_line_ids').mapped('order_id')
                                shopify_location_id = order_id.shopify_location_id or False
                                if not shopify_location_id:
                                    location_id = self.env['shopify.location.ept'].search(
                                        [('is_primary_location', '=', True),
                                         ('instance_id', '=', order_id.shopify_instance_id.id)])
                                    shopify_location_id = location_id.shopify_location_id or False
                                    if not location_id:
                                        message = "Primary Location not found for instance %s while Refund stock" % (
                                            order_id.shopify_instance_id.name)
                                        log = transaction_log_obj.search([('message', '=', message)])
                                        if not log:
                                            transaction_log_obj.create(
                                                {'message': message,
                                                 'mismatch_details': True,
                                                 'type': 'refund',
                                                 'shopify_instance_id': order_id.shopify_instance_id.id
                                                 })
                                        else:
                                            log.write({'message': message})
                                        not_process = True
                                        continue
                                refund_lines_dict.update({'location_id': shopify_location_id})
                            refund_lines_list.append(refund_lines_dict)

            in_picking_total_qty = 0
            out_picking_total_qty = 0
            shipping = {}
            for order in orders:
                outgoing_picking_ids = order.mapped('picking_ids').filtered(
                    lambda picking: picking.picking_type_id.code == 'outgoing' and picking.state == 'done')
                incoming_picking_ids = order.mapped('picking_ids').filtered(
                    lambda picking: picking.picking_type_id.code == 'incoming' and picking.state == 'done')

                if not outgoing_picking_ids:
                    break

                if incoming_picking_ids:
                    in_picking_total_qty = sum(incoming_picking_ids.mapped('move_lines').mapped('quantity_done'))
                if outgoing_picking_ids:
                    out_picking_total_qty = sum(outgoing_picking_ids.mapped('move_lines').mapped('quantity_done'))

                if in_picking_total_qty == out_picking_total_qty:
                    shipping.update({"full_refund": True})
                else:
                    shipping.update({'amount': 0.0})

            for order in orders:
                if not_process:
                    continue
                refund.shopify_instance_id.connect_in_shopify()
                refund_amount = refund.amount_total
                try:
                    transactions = shopify.Transaction().find(order_id=order.shopify_order_id)
                except Exception as error:
                    if error.response.code == 429 and error.response.msg == "Too Many Requests":
                        time.sleep(5)
                        transactions = shopify.Transaction().find(order_id=order.shopify_order_id)

                total_refund_in_shopify = 0.0
                total_order_amount = order.amount_total
                for transaction in transactions:
                    result = xml_to_dict(transaction.to_xml())
                    if result.get('transaction').get('kind') == 'sale':
                        parent_id = result.get('transaction').get('id')
                        gateway = result.get('transaction').get('gateway')
                    if result.get('transaction').get('kind') == 'refund' and result.get('transaction').get(
                            'status') == 'success':
                        refunded_amount = result.get('transaction').get('amount')
                        total_refund_in_shopify = total_refund_in_shopify + float(refunded_amount)
                total_refund_amount = total_refund_in_shopify + refund_amount
                maximum_refund_allow = refund_amount - total_refund_in_shopify
                if maximum_refund_allow < 0:
                    maximum_refund_allow = 0.0
                if total_refund_amount > total_order_amount:
                    raise UserError(_(
                        "You can't refund then actual payment, requested amount for refund %s, maximum refund allow %s") % (refund_amount, maximum_refund_allow))
                refund_in_shopify = shopify.Refund()
                vals = {'notify': notify,
                        "shipping": shipping,
                        "note": note,
                        "order_id": order.shopify_order_id,
                        "refund_line_items": refund_lines_list,
                        "transactions": [
                            {
                                "parent_id": parent_id,
                                "amount": refund_amount,
                                "kind": "refund",
                                "gateway": gateway,
                            }
                        ]
                        }
                refund_in_shopify.create(vals)
                refund.write({'is_refund_in_shopify': True})
        return True
