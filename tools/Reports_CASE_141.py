"""Reports browser test CASE-141."""

from playwright.sync_api import expect

from tools.reports_browser import ReportsBrowserCase


class ReportsCase141(ReportsBrowserCase):
    def test_case_141_reports(self):
        report = self.generate_monthly_report()
        self.assertEqual(report.report_type, 'monthly')
        expect(self.page.get_by_text('Report generated successfully!', exact=True)).to_be_visible()
        expect(self.page.get_by_role('heading', name='Generated Reports', exact=True)).to_be_visible()
        expect(self.generated_report_row(report)).to_be_visible()
