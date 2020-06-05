# -*- coding: utf-8 -*-
# Part of CAPTIVEA. Odoo 12 EE.                                  		 We add this!
																		#IF EXTENDING THE MODEL, NAME THIS FILE THE SAME AS THE MODEL YOU'RE EXTENDING
																		#IF CREATING NEW, NAME THE SAME AS THE NEW MODEL


from odoo import models, fields, api

class my_module(models.Model):											#Name this the same as the file overall
#
    _name = 'model.name'												#-------------------------------------- FIX THIS --------------------------------------------!!!!!!!!!
	_inherit = 'model.name'												#If inheriting, this should be the name of the model you're modifying

    name = fields.Char()												#These are the fields being added to the model
    value = fields.Integer()											#Make sure you keep them lowercase, they will AUTOMATICALLY be made uppercase in the database
    value2 = fields.Float(compute="_value_pc", store=True)				#Here we see one with parameter; It is a computed field which *stores* the values in the daatabase.
#																		 Important to note; Computed Values are readonly by default.
#																		 use the inverse='function' parameter to be able to set a value.
    description = fields.Text()											# https://www.odoo.com/documentation/13.0/reference/orm.html#models

    @api.depends('value')												#Here is where we do the math to compute... well... computed fields
#																		
    def _value_pc(self):												#Function name should be descriptive. And start with an underscore
        self.value2 = float(self.value) / 100							#------------------------------------- FIX THIS ---------------------------------------------!!!!!!!!!

#-----------------------------------------MORE EXAMPLE CODE ------------------------------------------------------------------------------------------------------------------
# -*- coding: utf-8 -*-
# Part of CAPTIVEA. Odoo 12 EE.
"""
from odoo import models, fields, api


class Opportunity(models.Model):
    _inherit = "crm.lead"

    custom_id = fields.Char(string='ID', store=True,
                            compute='_compute_custom_id')
    custom_project_id = fields.Char(string='Project ID', store=True,
                                    compute='_compute_custom_won_project_id')

    @api.depends('name')
    def _compute_custom_id(self):
        for rec in self:
            if rec.name:
                rec.custom_id = str(rec.id) + " - " + rec.name

    @api.depends('project_ids')
    def _compute_custom_won_project_id(self):
        for rec in self:
            if len(rec.project_ids) > 1:
                rec.custom_project_id = "%d - %s" % (
                    rec.project_ids[1].id, rec.project_ids[1].name)
"""   