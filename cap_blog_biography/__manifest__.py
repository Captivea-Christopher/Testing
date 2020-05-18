# -*- coding: utf-8 -*-
{
    'name': "cap_blog_biography",
    'summary': """
        Add Biography to partner""",
    'description': """
        Adds a Biography to the partner object. Shows this biography
        under the partners picture when posting in a blog.
    """,
    'author': "Christopher Beirne Captivea",
    'website': "https://www.Captivea.us/",
    'category': 'Website',
    'version': '0.1',
    'depends': ['base','website'],
    'data': [
        'views/blogpost.xml',
        'views/views.xml',
    ]
}