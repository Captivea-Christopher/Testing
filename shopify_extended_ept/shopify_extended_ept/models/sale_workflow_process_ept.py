from odoo import models, fields, api, _


#Created by Haresh Mori on date 20/06/209.This is used for create a fields in auto invoice work flow
class sale_workflow_process_extended(models.Model):
    _inherit = "sale.workflow.process.ept"

    create_credit_note = fields.Boolean('Create Credit Note',default=False,help="If it's check it will create a create a credit note")
    validate_credit_note = fields.Boolean(string='Validate Credit Note',default=False,help = "If it's check it will create credit note")
    register_payment_in_credit=fields.Boolean(string='Register Payment In Credit',default=False,help = "If it's check it will register the payment")
    
    @api.onchange("register_payment")
    def onchange_register_payment(self):
        for record in self:
            if not record.register_payment:
                record.create_credit_note=False
                
    @api.onchange("create_credit_note")
    def onchange_create_credit_note(self):
        for record in self:
            if not record.create_credit_note:
                record.validate_credit_note=False
                
    @api.onchange("create_credit_note")
    def onchange_create_credit_note(self):
        for record in self:
            if not record.create_credit_note:
                record.validate_credit_note=False
                
    
    
    
