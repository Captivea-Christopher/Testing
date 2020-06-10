# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class portal_task_submission(http.Controller):
	@http.route('/my/submit_task', type='http', auth='user', website=True)
	def index(self, **kw):
		partner_id = request.env.user.partner_id.id
		list_of_projects_owned_by_customer = request.env['project.project'].sudo().search([
			('partner_id', 'child of', partner_id)
		])
		return http.request.render('cap_portal_task_submission.portal_task_submission', {
			'list_of_projects_owned_by_customer': list_of_projects_owned_by_customer,
			})