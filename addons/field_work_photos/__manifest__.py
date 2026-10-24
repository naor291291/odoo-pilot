{
    "name": "Field Work - Before and After Photos",
    "version": "18.0.3.0.0",
    "summary": "Submit field photos for operations approval or correction",
    "license": "LGPL-3",
    "depends": ["project", "crm", "portal"],
    "data": [
        "security/field_review_security.xml", "security/field_dispatch_security.xml",
        "data/field_dispatch_data.xml", "views/project_task_views.xml",
        "views/field_dispatch_views.xml", "views/field_portal_templates.xml",
    ],
    "installable": True,
    "application": False,
}
