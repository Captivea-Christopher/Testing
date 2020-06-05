# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.addons.http_routing.models.ir_http import slug

class my_module(models.Model):
    _inherit = 'blog.post'

    custom_url = fields.Text()    #no uppercase, gets changed by the system
	
	 _sql_constraints = [
		('custom_url_unique', 'unique(custom_url)', 'There cannot be duplicate custom URLs')
		 ]

	    @api.multi
    def _compute_website_url(self):
        super(BlogPost, self)._compute_website_url()
        for blog_post in self:
            blog_post.website_url = "/odoo/%s" % (slug(blog_post.custom_url))