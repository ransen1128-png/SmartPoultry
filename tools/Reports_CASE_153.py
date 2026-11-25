"""Reports browser test CASE-153."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["153", *sys.argv[1:]]))


from tools.reports_browser import ReportsBrowserCase


class ReportsCase153(ReportsBrowserCase):
    def test_case_153_reports(self):
        report = self.generate_monthly_report()
        self.page.locator('#appDialog[open]').get_by_role(
            'button', name='Close notification', exact=True,
        ).click()
        with self.page.expect_download() as download:
            self.generated_report_row(report).get_by_role('link', name=f'Download {report.title} as Excel', exact=True).click()
        self.assertEqual(
            download.value.suggested_filename,
            f'monthly_report_{report.start_date}_to_{report.end_date}.xlsx',
        )
