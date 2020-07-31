from odoo import models,fields,api,_
from odoo.addons.shopify_ept import shopify
from odoo.addons.shopify_ept.shopify.pyactiveresource.util import xml_to_dict
from datetime import datetime
from dateutil import parser
import pytz
utc = pytz.utc
import time
import json

class SaleOrder(models.Model):
    _inherit = "sale.order"

    browser_ip = fields.Char(string = 'Browser IP', help = 'The IP address of the browser used by the customer when they placed the order.')
    credit_card_number = fields.Char(string = "Credit Card Number")
    promotion_code = fields.Char(string="Coupon Code")

    def open_shopify_orders(self):
        return {
                'type': 'ir.actions.act_url',
                 'url': 'https://%s/admin/draft_orders/%s'%(self.shopify_instance_id.shopify_host, self.shopify_order_id),
                 'nodestroy': True,
                'target': 'new'
            }

    def import_shopify_orders(self, order_data_queue_line, log_book_id):
        order_risk_obj = self.env['shopify.order.risk']
        transaction_log_obj = self.env["common.log.book.ept"]
        instance = log_book_id.shopify_instance_id
        order_data_queue_line.shopify_order_data_queue_id
        order_data = order_data_queue_line.order_data
        order_response = json.loads(order_data)
        order_response = order_response.get('order')
        instances = []
        if not instance:
            instances = self.env['shopify.instance.ept'].search([])
        else:
            instances.append(instance)
        for instance in instances:
            instance.connect_in_shopify()
            # if not from_date:
            #     from_date = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            # if not to_date:
            #     to_date = instance.last_date_order_import
            # instance.last_date_order_import = from_date
    
            """
            Changes related time zone issue @author Ekta bhut
            """
            # from_date = datetime.strptime(from_date, '%Y-%m-%d %H:%M:%S')
            # to_date = datetime.strptime(to_date, '%Y-%m-%d %H:%M:%S')
            # from_date = datetime.strptime(pytz.utc.localize(from_date).astimezone(
            #         pytz.timezone(instance.shopify_store_time_zone[12:] or 'UTC')).strftime(
            #         '%Y-%m-%d %H:%M:%S'), "%Y-%m-%d %H:%M:%S")
            # to_date = datetime.strptime(pytz.utc.localize(to_date).astimezone(
            #         pytz.timezone(instance.shopify_store_time_zone[12:] or 'UTC')).strftime(
            #         '%Y-%m-%d %H:%M:%S'), "%Y-%m-%d %H:%M:%S")
            shipped_orders = []
            for status in instance.import_shopify_order_status_ids:
                shopify_fulfillment_status = status.status
                if shopify_fulfillment_status == 'any' or shopify_fulfillment_status == 'shipped':
                    try:
                        order_ids = shopify.Order().find(status='any', fulfillment_status=shopify_fulfillment_status,
                                                         limit=250)
                    except Exception as e:
                        raise Warning(e)
                    if len(order_ids) >= 50:
                        order_ids = self.env['shopify.order.data.queue.ept'].list_all_orders(shopify_fulfillment_status)
                else:
                    try:
                        order_ids = shopify.Order().find(fulfillment_status=shopify_fulfillment_status,limit=250)
                    except Exception as e:
                        raise Warning(e)
                    if len(order_ids) >= 50:
                        order_ids = self.list_all_orders(shopify_fulfillment_status)
    
                for order_id in order_ids:
                    result = xml_to_dict(order_id.to_xml())
                    result = result.get('order')
    
                    if self.search(
                            [('shopify_order_id', '=', result.get('id')), ('shopify_instance_id', '=', instance.id),
                             ('shopify_order_number', '=', result.get('order_number'))]):
                        continue
    
                    if self.shopify_order_already_imported(result, instance):
                        continue
    
                    order_status = result.get('fulfillment_status', False)
                    if order_status == 'fulfilled' or order_status == 'partial':
                        if order_status == 'fulfilled':
                            shipped_orders.append(result.get('id', False))
                        all_tracking_numbers = []
                        for fullfillments in result.get('fulfillments', []):
                            tracking_numbers = fullfillments.get('tracking_numbers', [])
                            for tracking_number in tracking_numbers:
                                all_tracking_numbers.append(tracking_number)
                            shopify_track_numbers = ','.join(map(str, all_tracking_numbers))
    
                    partner = result.get('customer', {}) and self.create_or_update_customer(result.get('customer', {}),
                                                                                            True, False, False,
                                                                                            instance) or False
                    if not partner:
                        message = "Customer Not Available In %s Order" % (result.get('order_number'))
                        log = transaction_log_obj.search(
                            [('shopify_instance_id', '=', instance.id), ('message', '=', message)])
                        if not log:
                            transaction_log_obj.create(
                                {'message': message,
                                 # 'mismatch_details': True,
                                 'type': 'sales',
                                 'shopify_instance_id': instance.id
                                 })
                        continue
                    shipping_address = result.get('shipping_address', False) and self.create_or_update_customer(
                        result.get('shipping_address'), False, partner.id, 'delivery', instance) or partner
                    invoice_address = result.get('billing_address', False) and self.create_or_update_customer(
                        result.get('billing_address'), False, partner.id, 'invoice', instance) or partner
    
                    lines = result.get('line_items')
                    if self.check_mismatch_details(lines, instance, result.get('order_number'), order_data_queue_line, log_book_id):
                        continue
    
                    new_record = self.new({'partner_id': partner.id})
                    new_record.onchange_partner_id()
                    partner_result = self._convert_to_write({name: new_record[name] for name in new_record._cache})
    
                    fiscal_position = partner.property_account_position_id
                    pricelist_id = partner_result.get('pricelist_id', False)
                    payment_term = partner_result.get('payment_term_id') or False
    
                    # order = self.create_order(result, invoice_address, instance, partner, shipping_address,
                    #                          pricelist_id, fiscal_position, payment_term)
                    order = self.create_order(result, invoice_address, instance, partner, shipping_address,
                                              pricelist_id, fiscal_position)
    
                    if not order:
                        continue
                    risk_result = shopify.OrderRisk().find(order_id=order_id.id)
                    flag = False
                    for line in lines:
                        #                        if line.get('fulfillment_status'):
                        #                            continue
                        total_discount = result.get('total_discounts', 0.0)
                        shopify_product = self.create_or_update_product(line, instance)
                        if not shopify_product:
                            flag = True
                            break
                        product_url = shopify_product and shopify_product.producturl or False
                        if product_url:
                            line.update({'product_url': product_url})
                        product = shopify_product.product_id
                        # Addded by Ekta
    
                        tax_ids = self.get_tax_id_ept(instance, line.get('tax_lines'), result.get('taxes_included'))
                        self.create_sale_order_line(line, tax_ids, product, line.get('quantity'), fiscal_position,
                                                    partner, pricelist_id, product.name, order, line.get('price'))
                        if float(total_discount) > 0.0:
                            discount_allocations = line.get('discount_allocations')
                            total_discount_amount = 0.0
                            for discount_allocation in discount_allocations:
                                discount_amount = float(discount_allocation.get('amount', 0.0))
                                total_discount_amount += discount_amount
                            if total_discount_amount > 0.0 :
                                self.create_sale_order_line({}, tax_ids, instance.discount_product_id, 1, fiscal_position,
                                                        partner, pricelist_id, instance.discount_product_id.name, order,
                                                        float(total_discount_amount) * -1)
    
                    if flag:
                        order.unlink()
                        continue
    
                    """Changes taken By Jay Makwana Using Autoworkflow Validate one by one Orders"""
                    if risk_result:
                        order_risk_obj.create_risk(risk_result, order)
    
                    product_template_obj = self.env['product.template']
                    for line in result.get('shipping_lines', []):
                        tax_ids = self.get_tax_id_ept(instance, line.get('tax_lines'), result.get('taxes_included'))
                        delivery_method = line.get('title')
                        if delivery_method:
                            carrier = self.env['delivery.carrier'].search([('shopify_code', '=', delivery_method)],
                                                                          limit=1)
                            if not carrier:
                                carrier = self.env['delivery.carrier'].search(
                                    ['|', ('name', '=', delivery_method), ('shopify_code', '=', delivery_method)],
                                    limit=1)
                            if not carrier:
                                carrier = self.env['delivery.carrier'].search(['|', ('name', 'ilike', delivery_method),
                                                                               ('shopify_code', 'ilike',
                                                                                delivery_method)], limit=1)
                            if not carrier:
                                product_template = product_template_obj.search(
                                    [('name', '=', delivery_method), ('type', '=', 'service')], limit=1)
                                if not product_template:
                                    product_template = product_template_obj.create(
                                        {'name': delivery_method, 'type': 'service'})
                                carrier = self.env['delivery.carrier'].create(
                                    {'name': delivery_method, 'shopify_code': delivery_method,
                                     'partner_id': self.env.user.company_id.partner_id.id,
                                     'product_id': product_template.product_variant_ids[0].id})
                            order.write({'carrier_id': carrier.id})
                            if carrier.product_id:
                                shipping_product = carrier.product_id
                        self.create_sale_order_line(line, tax_ids, shipping_product, 1, fiscal_position, partner,
                                                    pricelist_id,
                                                    shipping_product and shipping_product.name or line.get('title'),
                                                    order, line.get('price'), is_shipping=True)
    
                    # if import_order_ids:
                    #     self.env['sale.workflow.process.ept'].auto_workflow_process(ids=import_order_ids)
    
                    """Addes By Jay Makwana If Shipped Orders than it will Validate Automatically Picking"""
                    if order:
                        self.env['sale.workflow.process.ept'].with_context({'order_date': order and order.date_order}).auto_workflow_process(ids=[order.id])
                        if int(order.shopify_order_id) in shipped_orders:
                            fullfill_order_picking = self.create_picking_for_fullfill_order(order,result,shopify_track_numbers)
    
                        if order_status == 'partial':
                            partial_order_picking = self.create_back_picking_for_partial_order(order,result,shopify_track_numbers)
    
    
                        """Add by Haresh mori on date 22/06/2019 This method for create a credit note in odoo while refund found from in Shopify order response"""
                        if result.get('financial_status') == 'refunded':
                            credit_note = self.create_full_credit_note(order,result)
                            if credit_note:
                                continue
    
                        if result.get('financial_status') == 'partially_refunded':
                            partially_credit_note = self.create_partially_credit_note(order,result)
                            if partially_credit_note:
                                continue
    
                    self._cr.commit()
            return True
        
    
    def create_picking_for_fullfill_order(self,order,order_response,shopify_track_numbers):
        """
        @author: Jay Makwana
        If Shipped Orders than it will Validate Automatically Picking
        """
        stock_move_line_obj = self.env['stock.move.line']
        stock_immediate_transfer_obj = self.env['stock.immediate.transfer']
        if order.state == "draft":
            order.action_confirm()
        for picking in order.picking_ids:
            if picking.state in ['waiting', 'confirmed']:
                picking.action_assign()
            if picking.state == 'assigned':
                for move in picking.move_lines:
                    if move.state == 'assigned' and move.product_uom_qty < 0:
                        for move_line in move.move_line_ids:
                            if move_line.product_uom_qty < 0:
                                move_line.write({'product_uom_qty': abs(move_line.product_uom_qty)})


                stock_immediate_transfer_obj.create({'pick_ids': [(4, picking.id)]}).with_context(
                    is_shipped_order=True).process()
            elif picking.state in ['confirmed', 'partially_available']:
                for move in picking.move_lines:
                    if move.state in ['confirmed', 'partially_available']:
                        remaining_qty = move.product_uom_qty - move.reserved_availability
                        if remaining_qty > 0.0:
                            stock_move_line_obj.create(
                                {
                                    'product_id': move.product_id.id,
                                    'product_uom_id': move.product_id.uom_id.id,
                                    'picking_id': picking.id,
                                    'qty_done': float(remaining_qty) or 0.0,
                                    'location_id': picking.location_id.id,
                                    'location_dest_id': picking.location_dest_id.id,
                                    'move_id': move.id,
                                })
       
                    if move.state == 'assigned':
                        if move.product_uom_qty < 0:
                            product_uom_qty = abs(move.product_uom_qty)
                        else:
                            product_uom_qty = move.product_uom_qty

                        move.write({'quantity_done' : product_uom_qty})


            picking.with_context(is_shipped_order=True).action_done()
            picking.write({'updated_in_shopify': True,'carrier_tracking_ref': shopify_track_numbers or ''})
        
        return True
                
    
    
    
    def create_back_picking_for_partial_order(self,order,order_response,shopify_track_numbers):
        """
        @author: Haresh Mori On date 25/06/2019
        @param param: order,response data
        @return: True
        This method used for create a back order picking if order is partially fulfilled is in Shopify
        @modify: Haresh Mori on date 07/08/2019 modification is managed the packed product in partially delivery order.
        """
        stock_immediate_transfer_obj = self.env['stock.immediate.transfer']
        stock_move_line_obj = self.env['stock.move.line']
        product_product_obj = self.env['product.product']
        if order.state == "draft":
            order.action_confirm()
        for fulfillments_lines in order_response.get('fulfillments'):
            lines = fulfillments_lines.get('line_items')
            shopify_line_id_list = []
            for line in lines:
                shopify_line_id = line.get('id') or False
                fulfilled_qty = line.get('quantity')
                if shopify_line_id:
                    shopify_line_id_list.append({'line_id':str(shopify_line_id),'qty':fulfilled_qty})
        for picking in order.picking_ids:
            if picking.state in ['waiting', 'confirmed']:
                picking.action_assign()
            for line in shopify_line_id_list:
                shopify_line_id = line.get('line_id')
                quantity = line.get('qty')
                sale_order_line_id = self.env['sale.order.line'].search([('shopify_line_id','=',shopify_line_id),('order_id','=',order.id)],limit = 1)
                pack_product_qty_list = []
                if sale_order_line_id.product_id.is_pack :
                    for pack_product in sale_order_line_id.product_id.wk_product_pack:
                        pack_product_qty = float(pack_product.product_quantity) * float(quantity)
                        pack_product_qty_list.append({'product_id': pack_product.product_id.id, 'qty':pack_product_qty })
                    move_lines = picking.move_lines.filtered(lambda ml:ml.sale_line_id.id == sale_order_line_id.id)
                    for move in move_lines:                        
                        for pack_product_move in pack_product_qty_list:
                            product_id = product_product_obj.browse(pack_product_move.get('product_id'))
                            if move.product_id.id == product_id.id:
                                move.move_line_ids and move.move_line_ids.unlink()
                                stock_move_line_obj.create(
                                        {
                                            'product_id': pack_product_move.get('product_id'),
                                            'product_uom_id': product_id.uom_id.id,
                                            'picking_id': picking.id,
                                            'qty_done':  abs(float(pack_product_move.get('qty')))
                                                         or 0.0,
                                            'location_id': picking.location_id.id,
                                            'location_dest_id': picking.location_dest_id.id,
                                            'move_id': move.id,
                                        })
                else :
                    move_lines = picking.move_lines.filtered(lambda ml:ml.sale_line_id.id == sale_order_line_id.id)
                    for move in move_lines:
                        if move.product_id.id == sale_order_line_id.product_id.id:
                            move.move_line_ids and move.move_line_ids.unlink()
                            stock_move_line_obj.create(
                                    {
                                        'product_id': move.product_id.id,
                                        'product_uom_id': move.product_id.uom_id.id,
                                        'picking_id': picking.id,
                                        'qty_done': float(quantity) or 0.0,
                                        'location_id': picking.location_id.id,
                                        'location_dest_id': picking.location_dest_id.id,
                                        'move_id': move.id,
                                    })
        
            picking.with_context(is_shipped_order=True).action_done()
            picking.write({'updated_in_shopify': True,'carrier_tracking_ref': shopify_track_numbers or ''})
        return True
    
    
    
    def create_full_credit_note(self,order,order_response):
        """
        @author: Haresh Mori On date 21/06/2019
        @param param: order,response data
        @return: True
        This method used for create a full_credit note while sale order import from shopify to odoo.base on sale auto invoice workflow it's work.
        """
        account_invoice_line_obj = self.env['account.invoice.line']
        account_invoice_obj = self.env['account.invoice']
        invoice = order.invoice_ids.filtered(lambda x: x.type == 'out_invoice' and x.state != 'cancel')
        invoice=self.env['account.invoice'].browse(invoice and invoice[0].id)
        if order_response.get('refunds'):
            for refund in order_response.get('refunds'):
                refund_invoice_vals = self.shopify_prepare_refund_invoice_vals(order,invoice,refund)
                refund_invoice_id = account_invoice_obj.create(refund_invoice_vals)
                if not refund_invoice_id:
                    return True
                for invoice_line in invoice.invoice_line_ids:
                    account_id = account_invoice_line_obj.get_invoice_line_account('out_refund', invoice_line.product_id, order.fiscal_position_id, order.company_id)
                    account_line_vals = ({
                        'product_id':invoice_line.product_id.id,
                        'name':invoice_line.name,
                        'quantity': invoice_line.quantity,
                        'invoice_line_tax_ids': [(6, 0, invoice_line.invoice_line_tax_ids.ids)],
                        'price_unit':invoice_line.price_unit,
                        'account_id':account_id and account_id.id,
                        'invoice_id': refund_invoice_id.id,
                        })
                    account_invoice_line_obj.create(account_line_vals)
                refund_invoice_id and refund_invoice_id.write({'reference':invoice.reference})
                refund_invoice_id and refund_invoice_id.compute_taxes()
                refund_invoice_id and refund_invoice_id.action_invoice_open()
                journal_id = order.auto_workflow_process_id.journal_id
                account_payment_obj = self.env['account.payment']
                if refund_invoice_id.state == 'open' :
                    ac_pay_values = {
                        'journal_id':journal_id.id,
                        'invoice_ids': [(6, 0, refund_invoice_id.ids)],
                        'currency_id':refund_invoice_id.currency_id.id,
                           'communication': refund_invoice_id.name,
                        'payment_type':'outbound',
                        'partner_id':refund_invoice_id.commercial_partner_id.id,
                        'amount':refund_invoice_id.residual,
                        'payment_method_id':order.auto_workflow_process_id.inbound_payment_method_id and order.auto_workflow_process_id.inbound_payment_method_id.id or order.auto_workflow_process_id.journal_id.inbound_payment_method_ids.id,
                        'partner_type':'customer'
                    }
                    account_payment_id = account_payment_obj.create(ac_pay_values)
                    account_payment_id.post()
        return True
    
    
    def create_partially_credit_note(self,order,order_response):
        """
        @author: Haresh Mori On date 24/06/2018
        @param param: order,response data
        @return: True
        This method used for create a partially credit note while sale order import from shopify to odoo.base on sale auto invoice workflow it's work.
        """
        account_invoice_line_obj = self.env['account.invoice.line']
        odoo_product_obj = self.env['product.product']
        account_invoice_obj = self.env['account.invoice']
        shopify_product_obj=self.env['shopify.product.product.ept']
        so_invoice = order.invoice_ids.filtered(lambda x: x.type == 'out_invoice' and x.state != 'cancel')
        if not so_invoice:
            return True
        #refund_invoice_vals = self.shopify_prepare_refund_invoice_vals(order,so_invoice)
        if order_response.get('refunds'):
            for refund in order_response.get('refunds'):
                #if the transaction not done we have only write the note in sale order 
                refund_invoice_vals = self.shopify_prepare_refund_invoice_vals(order,so_invoice,refund)
                refund_note = refund.get('note','')
                order_note = order.note or ''
                if refund_note:
                    note = order_note + '\n'  +refund_note
                    order.write({'note':note})  
                if not refund.get('transactions'):
                    continue
                refund_invoice_id = account_invoice_obj.create(refund_invoice_vals)
                refund_invoice_id.write({'comment':refund_note})
                if refund.get('order_adjustments'):
                    refund_amount = 0.0
                    for order_adjustment in refund.get('order_adjustments'):
                        amount = order_adjustment.get('amount') 
                        if amount:
                            amount = float(amount) * -1
                            refund_amount = refund_amount + amount 
                    product_id = so_invoice and so_invoice.invoice_line_ids and so_invoice.invoice_line_ids[0].product_id
                    account_id = account_invoice_line_obj.get_invoice_line_account('out_refund', product_id, order.fiscal_position_id, order.company_id)
                    account_invoice_line_obj.create({
                        'product_id': False,
                        'name': refund_invoice_vals and refund_invoice_vals.get('comment') or
                                _('Partial Refund From Shopify, An Order Is %s' % order.name),
                        'quantity': 1,
                        'invoice_line_tax_ids': [],
                        'price_unit': refund_amount,
                        'account_id':account_id and account_id.id or False,
                        'invoice_id': refund_invoice_id.id,
                    })
                if refund.get('refund_line_items'):
                    for product_line in refund.get('refund_line_items'):
                        sku = False
                        variant_id = False
                        sku = product_line.get('line_item').get('sku')
                        variant_id = product_line.get('line_item').get('variant_id')
                        product_qty = product_line.get('quantity')
                        product_price = product_line.get('subtotal')
                        odoo_product = odoo_product_obj.search([('default_code', '=', sku)], limit=1)
                        if not odoo_product and variant_id:
                            shopify_product=shopify_product_obj.search([('shopify_instance_id','=',order.shopify_instance_id.id),('variant_id','=',variant_id)])
                            sku = shopify_product and shopify_product.default_code or False
                            odoo_product = odoo_product_obj.search([('default_code', '=', sku)], limit=1)
                        invoice_line_id = so_invoice.invoice_line_ids.filtered(lambda x: x.product_id.id == odoo_product.id)
                        invoice_line_id = invoice_line_id and invoice_line_id[0]
                        account_id = account_invoice_line_obj.get_invoice_line_account('out_refund', odoo_product, order.fiscal_position_id, order.company_id)
        
                        vals = {
                            'product_id': odoo_product and odoo_product.id or False,
                            'name': invoice_line_id and invoice_line_id.name,
                            'quantity': product_qty,
                            'invoice_line_tax_ids': [(6, 0, invoice_line_id.invoice_line_tax_ids.ids)],
                            'price_unit': float(product_price)/product_qty if product_qty > 0 else float(product_price),
#                            'price_unit': product_line.get('line_item').get('price'),
                            'account_id': account_id and account_id.id or False,
                            'invoice_id': refund_invoice_id.id,
                        }
                        account_invoice_line_obj.create(vals)
#                         #Manage discount line 
#                         if product_line.get('line_item').get('discount_allocations'):
#                             for discount_amount in product_line.get('line_item').get('discount_allocations'):
#                                 amount = discount_amount.get('amount','')
#                                 if amount:
#                                     amount = float(amount) * -1
#                                     discount_product =  order.shopify_instance_id.discount_product_id
#                                     account_id = account_invoice_line_obj.get_invoice_line_account('out_refund', discount_product, order.fiscal_position_id, order.company_id)
#                                     vals = {
#                                             'product_id': discount_product and discount_product.id or False,
#                                             'name': 'Discount allocations for product sku %s'%(sku),
#                                             'quantity': 1,
#                                             'invoice_line_tax_ids': [(6, 0, [])],
#                                             'price_unit': amount,
#                                             'account_id': account_id and account_id.id or False,
#                                             'invoice_id': refund_invoice_id.id,
#                                         }
#                                     account_invoice_line_obj.create(vals)
                # If difference found in credit note then we have create a note in credit note with difference        
                refund_invoice_id and refund_invoice_id.write({'reference':so_invoice.reference})
                refund_invoice_id and refund_invoice_id.compute_taxes()
                total_refund_amount = 0.0 
                amount_difference = 0.0 
                for refund_transaction in refund.get('transactions'):
                    amount = float(refund_transaction.get('amount'))
                    total_refund_amount = total_refund_amount + amount
                if float(total_refund_amount) != float(refund_invoice_id.amount_total):
                    amount_difference = float(refund_invoice_id.amount_total) - float(total_refund_amount)
                    difference_note = "Refund amount difference is %s"%(round(amount_difference,2))
                    if  amount_difference != 0.0:
                        amount_difference = round((float(amount_difference) * -1),2)
                        invoice_credit_note = refund_invoice_id.comment or ''
                        note = invoice_credit_note + ' \n '+ difference_note
                        refund_invoice_id.write({'comment':note})
                        product_id = so_invoice and so_invoice.invoice_line_ids and so_invoice.invoice_line_ids[0].product_id
                        account_id = account_invoice_line_obj.get_invoice_line_account('out_refund', product_id, order.fiscal_position_id, order.company_id)
                        account_invoice_line_obj.create({
                        'product_id': False,
                        'name': 'Refund amount difference line',
                        'quantity': 1,
                        'invoice_line_tax_ids': [],
                        'price_unit': amount_difference,
                        'account_id':account_id and account_id.id or False,
                        'invoice_id': refund_invoice_id.id,
                        })
                refund_invoice_id and refund_invoice_id.compute_taxes()
                refund_invoice_id and refund_invoice_id.action_invoice_open()
                journal_id = order.auto_workflow_process_id.journal_id
                if refund_invoice_id.state == 'open' :
                    account_payment_obj = self.env['account.payment']
                    ac_pay_values = {
                   
                                      
                        'journal_id':journal_id.id,
                        'invoice_ids': [(6, 0, refund_invoice_id.ids)],
                        'currency_id':refund_invoice_id.currency_id.id,
                           'communication': refund_invoice_id.name,
                        'payment_type':'outbound',
                        'partner_id':refund_invoice_id.commercial_partner_id.id,
                        'amount':refund_invoice_id.residual,
                        'payment_method_id':order.auto_workflow_process_id.inbound_payment_method_id and order.auto_workflow_process_id.inbound_payment_method_id.id or order.auto_workflow_process_id.journal_id.inbound_payment_method_ids.id,
                        'partner_type':'customer'
                    }
                    account_payment_id = account_payment_obj.create(ac_pay_values)
                    account_payment_id.post()
        return True

    

    def shopify_prepare_refund_invoice_vals(self,order,so_invoice,refund):
        """
        @author: Haresh Mori On date 24/06/2018
        @param param: so_invoice
        @return: invoice_vals
        This method used for create a vals for  credit note while sale order import from Shopify to odoo.
        """
        date_refund = refund.get('processed_at', False)
        if date_refund:
            refund_date = parser.parse(date_refund).astimezone(utc).strftime('%Y-%m-%d %H:%M:%S')
        else:
            refund_date = time.strftime('%Y-%m-%d %H:%M:%S')
            refund_date = str(refund_date)

        invoice_vals = {
            'name': order.name or '',
            'origin': so_invoice and so_invoice.number or order.name,
            'type': 'out_refund',
            'user_id': so_invoice.user_id.id or order._uid or False,
            'refund_invoice_id': so_invoice.id,
            'account_id': order.partner_id.property_account_receivable_id.id,
            'partner_id': order.partner_invoice_id.id,
            'journal_id': so_invoice and so_invoice.journal_id.id or False,
            'currency_id': order.pricelist_id.currency_id.id or order.env.user.company_id.currency_id.id,
            'comment': order.note,
            'payment_term_id': order.payment_term_id and order.payment_term_id.id or False,
            'fiscal_position_id': order.fiscal_position_id and order.fiscal_position_id.id or False,
            'company_id': order.company_id.id,
            'date_invoice': refund_date or False,
            'team_id': order.team_id and order.team_id.id,
            'source_invoice_id': False,
            'shopify_instance_id':order.shopify_instance_id and order.shopify_instance_id.id,
            'is_refund_in_shopify':True,
        }
        return invoice_vals



    @api.model
    # def create_order(self, result, invoice_address, instance, partner, shipping_address, pricelist_id, fiscal_position,
    #                  payment_term):
    def create_order(self, result, invoice_address, instance, partner, shipping_address, pricelist_id, fiscal_position):
        """ Override this method for import those orders which has no payment getway and it will take default workflow from instance.
                            @author : Jay Makwana
                            @last_updated_on : 11th March, 2019
                        """
        pricelist = False
        shopify_payment_gateway = False
        no_payment_gateway = False
        payment_term_id = False
        gateway = result.get('gateway', '')
        currency= result.get('currency','')
        currency_id = self.env['res.currency'].search([('name', 'like',currency)],limit=1)
        pricelist = self.env['product.pricelist'].search([('currency_id', '=', currency_id.id)], limit=1)
        pricelist_id = pricelist and pricelist.id

        shopify_user_id = result.get('user_id', '')
        user_id = instance.shopify_salesperson_id.id or False

        if shopify_user_id:
            salesperson_id  = self.env['shopify.salesperson.instance.ept'].search([('instance_id','=',instance.id),('shopify_user_id','=',shopify_user_id)],limit=1)
            if salesperson_id:
                user_id = salesperson_id.user_id.id
            else:
                if not user_id:
                    user_id = self.env.uid
        else:
            if not user_id:
                user_id = self.env.uid

        if gateway:
            shopify_payment_gateway = self.env['shopify.payment.gateway.ept'].search(
                [('code', '=', gateway), ('shopify_instance_id', '=', instance.id)], limit=1)
            if not shopify_payment_gateway:
                shopify_payment_gateway = self.env['shopify.payment.gateway.ept'].create(
                    {'name': gateway, 'code': gateway, 'shopify_instance_id': instance.id})
        else:
            workflow = instance.default_auto_workflow_id
            if workflow:
                if not payment_term_id:
                    payment_term_id = False
                    # if payment_term_id:
                    #     partner.write({'property_payment_term_id': payment_term_id})
                shopify_payment_gateway = True
                no_payment_gateway = True
            else:
                transaction_log_obj = self.env["common.log.book.ept"]
                message = "Default Auto Workflow not set in Instance %s for order %s" % (
                instance.name, result.get('name'))
                log = transaction_log_obj.search([('shopify_instance_id', '=', instance.id), ('message', '=', message)])
            if not log:
                transaction_log_obj.create(
                    {'message': message,
                     # 'mismatch_details': True,
                     #'type': 'sales', 
                     'shopify_instance_id': instance.id
                     })
            return False

        if not shopify_payment_gateway:
            no_payment_gateway = self.verify_order(instance, result)
            if not no_payment_gateway:
                transaction_log_obj = self.env["common.log.book.ept"]
                message = "Payment Gateway not found for this order %s and financial status is %s" % (
                    result.get('name'), result.get('financial_status'))
                log = transaction_log_obj.search([('shopify_instance_id', '=', instance.id), ('message', '=', message)])
                if not log:
                    transaction_log_obj.create({'message': message,
                                                # 'mismatch_details': True,
                                                # 'type': 'sales', 
                                                'shopify_instance_id': instance.id
                                                })
                    return False

        workflow = False
        if not no_payment_gateway and shopify_payment_gateway:
            workflow_config = self.env['sale.auto.workflow.configuration'].search(
                [('shopify_instance_id', '=', instance.id), ('payment_gateway_id', '=', shopify_payment_gateway.id),
                 ('financial_status', '=', result.get('financial_status'))])
            workflow = workflow_config and workflow_config.auto_workflow_id or False
            if workflow_config:
                payment_term_id = workflow_config.payment_term_id and workflow_config.payment_term_id.id or False
                if not payment_term_id:
                    payment_term_id = False
                    # if payment_term_id:
                    #     partner.write({'property_payment_term_id': payment_term_id})

        if not workflow and not no_payment_gateway:
            transaction_log_obj = self.env["common.log.book.ept"]
            message = "Workflow Configuration not found for this order %s and payment gateway is %s and financial status is %s" % (
                result.get('name'), gateway, result.get('financial_status'))
            log = transaction_log_obj.search([('shopify_instance_id', '=', instance.id), ('message', '=', message)])
            if not log:
                transaction_log_obj.create(
                    {'message': message,
                     # 'mismatch_details': True,
                     # 'type': 'sales', 
                     'shopify_instance_id': instance.id
                     })
            return False

        if not gateway:
            shopify_payment_gateway = False

        credit_card_number = ''
        browser_ip = ''
        if result.get('client_details',) and result.get('client_details',).get('browser_ip'):
            browser_ip = result.get('client_details', ).get('browser_ip') or ''
        
        if result.get('payment_details') and result.get('payment_details',).get('credit_card_number'):
            credit_card_number = result.get('payment_details', ).get('credit_card_number') or ''

        coupon_code = ''
        flag = 1
        for discount_code in result.get('discount_codes'):
            if discount_code.get('code', False):
                if flag:
                    coupon_code = discount_code.get('code', False)
                    flag = 0
                else:
                    coupon_code = coupon_code + ',' + discount_code.get('code', False)
        
        if result.get('created_at',False):
            order_date=result.get('created_at',False)
            date_order=parser.parse(order_date).astimezone(utc).strftime('%Y-%m-%d %H:%M:%S')
        else:
            date_order=time.strftime('%Y-%m-%d %H:%M:%S')        
            date_order=str(date_order)

        ordervals = {
            'checkout_id': result.get('checkout_id'),
            'partner_invoice_id': invoice_address.ids[0],
            'date_order': date_order,
            'warehouse_id': instance.warehouse_id.id,
            'partner_id': partner.ids[0],
            'partner_shipping_id': shipping_address.ids[0],
            'state': 'draft',
            'pricelist_id': pricelist_id or False,
            'fiscal_position_id': fiscal_position and fiscal_position.id or False,
            'note': result.get('note'),
            'shopify_order_id': result.get('id'),
            'shopify_order_number': result.get('order_number'),
            'shopify_payment_gateway_id': shopify_payment_gateway and shopify_payment_gateway.id or False,
            'shopify_instance_id': instance.id,
            'team_id': instance.section_id and instance.section_id.id or False,
            'company_id': instance.company_id.id,
            'global_channel_id': instance.global_channel_id and instance.global_channel_id.id or False,
            'shopify_location_id': result.get('location_id'),
            'browser_ip':browser_ip or '',
            'credit_card_number': credit_card_number or '',
            'user_id':user_id,
            'promotion_code':coupon_code or '',
        }

        if not instance.is_use_default_sequence:
            if instance.order_prefix:
                name = "%s_%s" % (instance.order_prefix, result.get('name'))
            else:
                name = result.get('name')
            ordervals.update({'name': name})

        if workflow:
            ordervals.update({
                'picking_policy': workflow.picking_policy,
                'auto_workflow_process_id': workflow.id,
                'payment_term_id': payment_term_id and payment_term_id or payment_term or False,
                'invoice_policy': workflow.invoice_policy or False
            })
        order = self.create(ordervals)
        order.with_context({'is_shopify_order': True}).onchange_partner_shipping_id()
        return order

    @api.model
    def get_tax_id_ept(self, instance, order_line, tax_included):
        """ Override this method for 01) add tax search criteria based on name + rate 02) set default accound and refund account as per set in instance.
                    @author : Jay Makwana
                    @last_updated_on : 05th March, 2019
                """
        refund_account_id = instance.refund_account_id
        account_id = instance.account_id
        tax_id = []
        taxes = []
        for tax in order_line:
            tax_rate = float(tax.get('rate', 0.0))
            price = float(tax.get('price', 0.0))  # Ekta
            rate = tax_rate * 100
            if rate != 0.0 and price > 0.0:

                if tax_included:
                    name = '%s (%s%s)' % (tax.get('title'), str(round(rate, 4)), '%')
                else:
                    name = '%s (%s%s)' % (tax.get('title'), str(round(rate, 4)), '%')

                acctax_id = self.env['account.tax'].search(
                    [('name', '=', name), ('price_include', '=', tax_included), ('type_tax_use', '=', 'sale'),
                     ('amount', '=', (round(rate, 4))),
                     ('company_id', '=', instance.warehouse_id.company_id.id)], limit=1)
                if not acctax_id:
                    acctax_id = self.createAccountTax(tax.get('rate', 0.0), tax_included,
                                                      instance.warehouse_id.company_id,
                                                      tax.get('title'))
                    if acctax_id:
                        if account_id and refund_account_id:
                            acctax_id.write({'account_id': account_id.id,
                                             'refund_account_id': refund_account_id.id})

                        transaction_log_obj = self.env["common.log.book.ept"]
                        message = """Tax was not found in ERP ||
                            Automatic Created Tax,%s ||
                            tax rate  %s ||
                            Company %s""" % (acctax_id.name, tax_rate, instance.company_id.name)
                        transaction_log_obj.create(
                            {'message': message,
                             # 'mismatch_details': True,
                             # 'type': 'sales',
                             'shopify_instance_id': instance.id
                             })
                if acctax_id:
                    if not acctax_id.account_id and not acctax_id.refund_account_id:
                        acctax_id.write({'account_id': account_id.id,
                                         'refund_account_id': refund_account_id.id})
                    taxes.append(acctax_id.id)
        if taxes:
            tax_id = [(6, 0, taxes)]

        return tax_id

    @api.model
    def createAccountTax(self, value, price_included, company, title):
        """ Override this method for create tax based on their name and rate.
                    @author : Jay Makwana
                    @last_updated_on : 05th March, 2019
                """
        accounttax_obj = self.env['account.tax']

        rate = value * 100
        tax_amount = round(float(value) * 100, 4)

        if price_included:
            name = '%s (%s%s)' % (title, str(tax_amount), '%')
        else:
            name = '%s (%s%s)' % (title, str(tax_amount), '%')

        accounttax_id = accounttax_obj.create(
            {'name': name, 'amount': tax_amount, 'type_tax_use': 'sale', 'price_include': price_included,
             'company_id': company.id})

        return accounttax_id
    
    
    @api.model
    def update_order_status(self, instance):
        """
        @author Ekta bhut
        :param instance: Shopify Instance
        :return: True
        This method is changed due to changes of speed up and some other changes related pack
        product.
        """
        move_line_obj = self.env['stock.move.line']
        transaction_log_obj = self.env["common.log.book.ept"]
        stock_picking_obj = self.env['stock.picking']
        log = False
        instances = []
        if not instance:
            instances = self.env['shopify.instance.ept'].search(
                    [('shopify_order_auto_import', '=', True)])
        else:
            instances.append(instance)
        for instance in instances:
            instance.connect_in_shopify()
            picking_ids = stock_picking_obj.search([('state', '=', 'done'),
                                                    ('is_shopify_delivery_order', '=', True),
                                                    ('shopify_instance_id', '=',instance.id),
                                                    ('updated_in_shopify', '!=', 'True')])

            for picking in picking_ids:
                # if picking.updated_in_shopify:
                #     continue
                sale_order = picking.sale_id
                notify_customer = instance.notify_customer
                order = shopify.Order.find(sale_order.shopify_order_id)
                # for picking in sale_order.picking_ids:
                #     """Here We Take only done picking and  updated in shopify false"""
                #     if picking.updated_in_shopify or picking.state != 'done':
                #         continue

                line_items = {}
                #list_of_tracking_number = []
                tracking_numbers = []
                tracking_no = ''
                list_of_tracking_number = picking.move_line_ids.filtered(lambda  l :
                                                                         l.result_package_id.tracking_no).mapped('result_package_id').mapped('tracking_no') or  []
                picking.carrier_tracking_ref and list_of_tracking_number.append(
                        picking.carrier_tracking_ref)
                carrier_name = picking.carrier_id and picking.carrier_id.shopify_code or ''
                if not carrier_name:
                    carrier_name = picking.carrier_id and picking.carrier_id.name or ''
                for move in picking.move_lines:
                    shopify_line_id = ''
                    if move.sale_line_id and move.sale_line_id.shopify_line_id:
                        shopify_line_id = move.sale_line_id.shopify_line_id
                    if move.product_id.id != move.sale_line_id.product_id.id:
                        product_qty = move.sale_line_id.product_uom_qty
                    else:
                        move_line = move_line_obj.search([('move_id', '=', move.id), (
                        'product_id', '=', move.product_id.id)])
                        product_qty = sum(move_line.mapped('qty_done')) or 0.0

                    product_qty = int(product_qty)
                    if shopify_line_id in line_items:
                        #if 'tracking_no' in line_items.get(shopify_line_id):
                        quantity = line_items.get(shopify_line_id).get('quantity')
                        #quantity = quantity + product_qty
                        line_items.get(shopify_line_id).update({'quantity':quantity})
                    else:
                        line_items.update({shopify_line_id:{}})
                        #line_items.get(shopify_line_id).update({'tracking_no':[]})
                        line_items.get(shopify_line_id).update({'quantity':product_qty})
                        #line_items.get(shopify_line_id).get('tracking_no').append(tracking_no)

                update_lines = []
                for sale_line_id in line_items:
                    #tracking_numbers += line_items.get(sale_line_id).get('tracking_no')
                    # tracking_numbers.append(picking.carrier_tracking_ref)
                    update_lines.append({'id':sale_line_id,
                                         'quantity':line_items.get(sale_line_id).get(
                                             'quantity')})
                if not update_lines:
                    message = "No lines found for update order status for %s" % (picking.name)
                    log = transaction_log_obj.search([('shopify_instance_id', '=', instance.id),
                                                      ('message', '=', message)])
                    if not log:
                        transaction_log_obj.create(
                                {'message':message,
                                 # 'mismatch_details':True,
                                 # 'type':'sales',
                                 'shopify_instance_id':instance.id
                                 })
                    continue
                try:
                    shopify_location_id = sale_order.shopify_location_id or False
                    if not shopify_location_id:
                        location_id = self.env['shopify.location.ept'].search(
                                [('is_primary_location', '=', True),
                                 ('instance_id', '=', instance.id)])
                        shopify_location_id = location_id.shopify_location_id or False
                        if not location_id:
                            message = "Primary Location not found for instance %s while Update order status" % (
                                instance.name)
                            if not log:
                                transaction_log_obj.create(
                                        {'message':message,
                                         # 'mismatch_details':True,
                                         # 'type':'stock',
                                         'shopify_instance_id':instance.id
                                         })
                            continue
                    new_fulfillment = shopify.Fulfillment(
                            {'order_id':order.id, 'location_id':shopify_location_id,
                             'tracking_numbers':list(set(list_of_tracking_number)),
                             'tracking_company':carrier_name, 'line_items':update_lines,
                             'notify_customer':notify_customer})
                    new_fulfillment.save()
                except Exception as e:
                    raise Warning(e)
                picking.write({'updated_in_shopify':True})
        self.closed_at(instances)
        return True

    def create_or_update_customer(self, vals, is_company=False, parent_id=False, type=False,
                                  instance=False):
        shopify_customer_detail_obj = self.env['shopify.customer.details.ept']
        country_obj = self.env['res.country']
        state_obj = self.env['res.country.state']
        partner_obj = self.env['res.partner']
        email = vals.get('email')
        if is_company:
            address = vals.get('default_address')
            if not address:
                address = vals
            customer_id = address.get('customer_id') or address.get('id')
            name = address.get('name') or "%s %s" % (vals.get('first_name'), vals.get('last_name'))

            company_name = address.get("company")
            phone = address.get('phone')
            # opt_out = vals.get('accepts_marketing')

            state_name = address.get('province')
            state_code = address.get('province_code')

            zip = address.get('zip')

            city = address.get('city')
            address1 = address.get('address1')
            address2 = address.get('address2')

            country_name = address.get('country')
            country_code = address.get('country_code')
            country = False
            if country_code:
                country = country_obj.search([('code', '=', country_code)], limit=1)
            else:
                country = country_obj.search([('name', '=', country_name)], limit=1)

            if not country:
                country = country_obj.search([('name', '=', country_name)], limit=1)

            if not country:
                state = state_obj.search([('code', '=', state_code)], limit=1)
            else:
                state = state_obj.search(
                    [('code', '=', state_code), ('country_id', '=', country.id)], limit=1)

            if not state:
                if not country:
                    state = state_obj.search([('name', '=', state_name)], limit=1)
                else:
                    state = state_obj.search(
                        [('name', '=', state_name), ('country_id', '=', country.id)], limit=1)
            if len(state.ids) > 1:
                state = state_obj.search([('code', '=', state_code), ('name', '=', state_name)],
                                         limit=1)

            # partner=self.env['res.partner'].search([('name','=',name),('state_id','=',state.id),('city','=',city),('zip','=',zip),('street','=',address1),('street2','=',address2),('country_id','=',country.id)],limit=1)
            customer_detail = shopify_customer_detail_obj.search([('shopify_customer_id', '=',
                                                                   customer_id),
                                                                  ('instance_id', '=', instance.id),('partner_id','!=',False)],limit=1)
            partner = customer_detail.partner_id
            # partner = partner_obj.search([('shopify_customer_id', '=', customer_id)], limit=1)
            if partner:
                partner.write({'name': name,'state_id': state and state.id or False, 'city': city,
                               'street': address1, 'street2': address2, 'country_id': country.id,
                               'is_company': True,
                               # 'property_payment_term_id': instance.payment_term_id.id,
                               'parent_id': False, 'zip': zip, 'email': email,
                               # 'company_name_ept': company_name, 'phone': phone
                               })
            else:
                partner = partner_obj.create({'shopify_customer_id': customer_id, 'name': name,
                                              'state_id': state and state.id or False, 'city': city,
                                              'street': address1, 'street2': address2,
                                              'country_id': country and country.id or False,
                                              'is_company': True,
                                              # 'property_payment_term_id': instance.payment_term_id.id,
                                              'property_product_pricelist': instance.pricelist_id.id,
                                              'property_account_position_id': instance.fiscal_position_id and instance.fiscal_position_id.id or False,
                                              'zip': zip, 'email': email,
                                              # 'company_name_ept': company_name, 'phone': phone
                                              })
                shopify_customer_detail_obj.create({'partner_id': partner.id,
                                                    'shopify_customer_id': customer_id,
                                                    'instance_id': instance.id})
            return partner
        else:
            customer_id = vals.get('customer_id') or False
            name = vals.get('name')
            company_name = vals.get("company")
            phone = vals.get('phone')
            state_name = vals.get('province')
            state_code = vals.get('province_code')
            city = vals.get('city')
            zip = vals.get('zip')
            street = vals.get('address1')
            street1 = vals.get('address2')

            country_name = vals.get('country')
            country_code = vals.get('country_code')

            country = country_obj.search([('code', '=', country_code)])
            if not country:
                country = country_obj.search([('name', '=', country_name)])

            if not country:
                state = state_obj.search([('code', '=', state_code)])
            else:
                state = state_obj.search(
                    [('code', '=', state_code), ('country_id', '=', country.id)])

            if not state:
                if not country:
                    state = state_obj.search([('name', '=', state_name)])
                else:
                    state = state_obj.search(
                        [('name', '=', state_name), ('country_id', '=', country.id)])

            if len(state.ids) > 1:
                state = state_obj.search([('code', '=', state_code), ('name', '=', state_name)])

            address = self.env['res.partner'].search(
                [('name', '=', name), ('state_id', '=', state.id), ('city', '=', city),
                 ('zip', '=', zip), ('street', '=', street), ('street2', '=', street1),
                 ('country_id', '=', country.id)], limit=1)
            if not address:
                address = self.env['res.partner'].create(
                    {'name': name, 'state_id': state.id, 'city': city, 'zip': zip, 'street': street,
                     'street2': street1,
                     'country_id': country.id, 'parent_id': parent_id, 'type': type, 'email': email,
                     # 'company_name_ept': company_name, 'phone': phone
                     })
            shopify_customer_detail_obj.create({'partner_id': address.id,
                                                'shopify_customer_id': customer_id,
                                                'instance_id': instance.id})
            return address

    def shopify_order_already_imported(self, order_result, instance):
        """
        Use: To Check order is already imported or not.
        Added by: Jay Makwana @Emipro Technologies
        Added on: 8/1/20
        :param result: Shopify order response, Dict of values.
        :return: True or False
        """
        sale_order_obj = self.env['sale.order']
        address = order_result.get('default_address')
        already_imported = False
        if not address:
            address = order_result.get('customer', {})
        customer_id = address.get('customer_id') or address.get('id')

        draft_orders = sale_order_obj.search(
            [('shopify_instance_id', '=', instance.id), ('exported_in_shopify', '=', True),('shopify_order_imported','=',False),
             ('shopify_customer_id', '=', str(customer_id))])
        for order in draft_orders:
            if order.shopify_order_id:
                draft_order_result = shopify.DraftOrder.find(order.shopify_order_id)
                result = xml_to_dict(draft_order_result.to_xml())
                if result.get('draft_order').get('status') == 'completed' and result.get('draft_order').get('order_id') == order_result.get('id'):
                    self.set_workflow_and_payment_details(order, order_result, instance)
                    self.set_shopify_order_line_id(order_result, instance, order)
                    order.write({'shopify_order_id': order_result.get('id'),
                                 'shopify_order_number': order_result.get('order_number'),
                                 'client_order_ref': order_result.get('name'),
                                 'note': order_result.get('note'),
                                 'shopify_order_imported':True,
                                 })
                    already_imported = True
                    break
        return already_imported


    def set_shopify_order_line_id(self, result, instance, order):
        """
        Use: To set shopify order line id in odoo order.
        Added by: Jay Makwana @Emipro Technologies
        Added on: 10/2/20
        """
        order_line_obj = self.env['sale.order.line']
        shopify_product_obj = self.env['shopify.product.product.ept']
        line_items = result.get('line_items', [])
        shipping_lines = result.get('shipping_lines', [])
        for line in line_items:
            shopify_variant_id = shopify_product_obj.search(
                [('shopify_instance_id', '=', instance.id), ('variant_id', '=', line.get('variant_id'))], limit=1)
            if shopify_variant_id:
                order_line = order_line_obj.search(
                    [('order_id', '=', order.id), ('product_id', '=', shopify_variant_id.product_id.id)])
                if order_line:
                    order_line.write({'shopify_line_id': line.get('id')})
        for shipping_line in shipping_lines:
            order_line = order.mapped('order_line').filtered(lambda line: line.product_id.is_shipping_product == True)
            if order_line:
                order_line.write({'shopify_line_id': shipping_line.get('id')})
        return True

    def set_workflow_and_payment_details(self, order, order_result, instance):
        """
        Use: To set workflow, payment details and other order information.
        Added by: Jay Makwana @Emipro Technologies
        Added on: 7/2/20
        """
        shopify_payment_gateway_obj = self.env['shopify.payment.gateway.ept']
        transaction_log_obj = self.env["common.log.book.ept"]
        gateway = order_result.get('gateway', '')
        no_payment_gateway = False
        payment_term_id = False
        if gateway:
            shopify_payment_gateway = shopify_payment_gateway_obj.search(
                [('code', '=', gateway), ('shopify_instance_id', '=', instance.id)], limit=1)
            if not shopify_payment_gateway:
                shopify_payment_gateway = shopify_payment_gateway_obj.create({
                    'name': gateway, 'code': gateway, 'shopify_instance_id': instance.id
                })
        else:
            workflow = instance.default_auto_workflow_id
            if workflow:
                if not payment_term_id:
                    payment_term_id = False
                    # if payment_term_id:
                    #     order.partner_id.write({'property_payment_term_id': payment_term_id})
                shopify_payment_gateway = True
                no_payment_gateway = True
            else:
                message = "Default Auto Workflow not set in Instance %s for order %s" % (instance.name, order.name)
                log = transaction_log_obj.search([('shopify_instance_id', '=', instance.id), ('message', '=', message)])
                if not log:
                    transaction_log_obj.create(
                        {'message': message,
                        # 'mismatch_details': True,
                        # 'type': 'sales', 
                        'shopify_instance_id': instance.id
                    })
        return False

        if not shopify_payment_gateway:
            no_payment_gateway = self.verify_order(instance, order_result)
            if not no_payment_gateway:
                transaction_log_obj = self.env["common.log.book.ept"]
                message = "Payment Gateway not found for this order %s and financial status is %s" % (
                    order_result.get('name'), order_result.get('financial_status'))
                log = transaction_log_obj.search([('shopify_instance_id', '=', instance.id), ('message', '=', message)])
                if not log:
                    transaction_log_obj.create({'message': message,
                                                # 'mismatch_details': True,
                                                # 'type': 'sales', 
                                                'shopify_instance_id': instance.id
                                                })
                    return False

        if not no_payment_gateway and shopify_payment_gateway:
            workflow_config = self.env['sale.auto.workflow.configuration'].search(
                [('shopify_instance_id', '=', instance.id), ('payment_gateway_id', '=', shopify_payment_gateway.id),
                 ('financial_status', '=', order_result.get('financial_status'))])
            workflow = workflow_config and workflow_config.auto_workflow_id or False
            if workflow_config:
                payment_term_id = workflow_config.payment_term_id and workflow_config.payment_term_id.id or False
                if not payment_term_id:
                    payment_term_id = False
                    # if payment_term_id:
                    #     order.partner_id.write({'property_payment_term_id': payment_term_id})

        if not workflow and not no_payment_gateway:
            transaction_log_obj = self.env["common.log.book.ept"]
            message = "Workflow Configuration not found for this order %s and payment gateway is %s and financial status is %s" % (
                order_result.get('name'), gateway, order_result.get('financial_status'))
            log = transaction_log_obj.search([('shopify_instance_id', '=', instance.id), ('message', '=', message)])
            if not log:
                transaction_log_obj.create({
                    'message': message,
                     # 'mismatch_details': True,
                     # 'type': 'sales',
                     'shopify_instance_id': instance.id
                     })
            return False

        if workflow:
            order.write({
                'picking_policy': workflow.picking_policy,
                'auto_workflow_process_id': workflow.id,
                'payment_term_id': False,
                'invoice_policy': workflow.invoice_policy or False,
            })
        return True
