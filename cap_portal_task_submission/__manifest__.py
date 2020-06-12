# -*- coding: utf-8 -*-
{
    'name': "cap_portal_task_submission",

    'summary': """
        Adds customer task submission page
        """,

    'description': """
        Adds a new webpage which allows a customer to submit a task directly to a project
        that belongs to the company that the customer belongs to. 
        Updates the My Account Page to include a button, which only appears if that customer
        belongs to a company which is the customer on at least one project.
        This button links to a task submission page, which takes in a project (to link the new
        task to), a Required task name, and a description of the task. Upon submission of the new task
        the user will be redirected back to the "My Account" page.
        
        Note: This requires that all customers are correctly linked to their company through the
        contact page (res.partner model).
    """,

    'author': "Christopher Beirne Captivea",
    'website': "https://www.Captivea.us/",

    'category': 'Uncategorized',
    'version': '0.2',

    'depends': ['base','website','project','contacts', 'website_form'],

    'data': [
        'views/templates.xml',
        'data/data.xml',
    ]
}