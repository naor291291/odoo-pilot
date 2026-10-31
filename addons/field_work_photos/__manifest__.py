{
    "name": "Field Work - Before and After Photos",
    "version": "18.0.10.0.0",
    "summary": "Submit field photos for operations approval or correction",
    "license": "LGPL-3",
    "depends": ["project", "crm", "portal"],
    "data": [
        "security/field_review_security.xml", "security/field_dispatch_security.xml", "security/ir.model.access.csv",
        "data/field_dispatch_data.xml", "views/project_task_views.xml",
        "views/field_dispatch_views.xml", "views/field_pricing_views.xml", "views/field_workspace_views.xml", "views/field_portal_templates.xml",
        "security/field_collection_security.xml", "views/field_collection_views.xml",
        "views/field_interface_views.xml", "views/field_navigation_views.xml",
    ],
    "assets": {
        "web.assets_backend": ["field_work_photos/static/src/scss/field_theme.scss", "field_work_photos/static/src/scss/field_dispatch.scss", "field_work_photos/static/src/scss/field_interface.scss", "field_work_photos/static/src/scss/field_crm.scss"],
        "web.assets_frontend": ["field_work_photos/static/src/scss/field_theme.scss", "field_work_photos/static/src/scss/field_interface.scss", "field_work_photos/static/src/scss/field_crm.scss", "field_work_photos/static/src/js/field_portal.js"],
    },
    "installable": True,
    "application": False,
}
