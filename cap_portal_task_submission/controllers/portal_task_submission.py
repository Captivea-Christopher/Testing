# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class portal_task_submission(http.Controller):
	@http.route('/my/submit_task', type='http', auth='user', website=True)
	def index(self, **kw):
		partner_id = request.env.user.partner_id.parent_id.id
		list_of_projects_owned_by_customer = request.env['project.project'].sudo().search([
        '|',
            '&',
                ('project_id.privacy_visibility', '=', 'portal'),
                ('project_id.message_partner_ids', 'child_of', [request.user.partner_id.commercial_partner_id.id]),
            '&',
                ('project_id.privacy_visibility', '=', 'portal'),
                ('message_partner_ids', 'child_of', [request.user.partner_id.commercial_partner_id.id]),
        ])
		projects_exist = list_of_projects_owned_by_customer.exists()
		return http.request.render('cap_portal_task_submission.portal_task_submission', {
			'list_of_projects_owned_by_customer': list_of_projects_owned_by_customer,
			'projects_exist' : projects_exist
			})