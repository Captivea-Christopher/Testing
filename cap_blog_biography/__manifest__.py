# -*- coding: utf-8 -*-
{
    'name': "cap_blog_biography",
    'summary': """
        Add Biography to partner""",
    'description': """
        Adds a Biography to the partner object. This Biography
	field is shown on the contact page of partners belonging
	to the "Captivea LLC" or "Captivea France" companies (Id's 
	1 & 102). 
	Shows this biography alongside the partners name and picture,
	as well as the publishing date when posting a blogpost.
    """,
    'author': "Christopher Beirne Captivea",
    'website': "https://www.Captivea.us/",
    'category': 'Website',
    'version': '1.0',
    'depends': ['base','website','website_blog'],
    'data': [
        'views/blogpost.xml',
        'views/views.xml',
    ]
} 