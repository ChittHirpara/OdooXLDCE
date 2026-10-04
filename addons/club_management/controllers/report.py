import csv
import io

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request


class ClubReportController(http.Controller):

    @http.route('/club/report.csv', type='http', auth='user', methods=['GET'])
    def report_csv(self, period='month', **kw):
        """The owner dashboard numbers as a spreadsheet file. Club managers only."""
        try:
            rows = request.env['club.dashboard'].report_rows(period)
        except AccessError:
            return request.not_found()
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(['Section', 'Measure', 'Value'])
        writer.writerows(rows)
        filename = 'champions-club-%s.csv' % (period if period in ('today', 'week', 'month', 'all') else 'month')
        return request.make_response(out.getvalue(), headers=[
            ('Content-Type', 'text/csv; charset=utf-8'),
            ('Content-Disposition', 'attachment; filename="%s"' % filename)])
