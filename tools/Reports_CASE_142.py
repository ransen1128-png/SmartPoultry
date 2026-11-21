"""Reports browser test CASE-142."""

from playwright.sync_api import expect

from tools.reports_browser import ReportsBrowserCase


class ReportsCase142(ReportsBrowserCase):
    def test_case_142_reports(self):
        report = self.generate_monthly_report()
        notification = self.page.locator('#appDialog[open]')
        expect(notification.get_by_text('Report generated successfully!', exact=True)).to_be_visible()
        notification.get_by_role('button', name='Close notification').click()
        expect(notification).to_be_hidden()
        with self.page.expect_download() as download:
            self.generated_report_row(report).get_by_role('button', name='Download', exact=True).click()
        self.assertEqual(
            download.value.suggested_filename,
            f'monthly_report_{report.start_date}_to_{report.end_date}.csv',
        )
