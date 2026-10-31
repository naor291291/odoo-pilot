"""Keep private statement responses out of shared and persistent caches."""
from odoo import http
from odoo.addons.web.controllers.report import ReportController


class ContractorStatementController(ReportController):
    @http.route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        # Preserve native authentication, report-provider access checks and the
        # download route (which calls this method) before setting cache policy.
        response = super().report_routes(reportname, docids=docids, converter=converter, **data)
        if reportname == 'field_work_photos.contractor_statement_pdf':
            response.headers['Cache-Control'] = 'private, no-store'
        return response
