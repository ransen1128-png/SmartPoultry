"""Reports browser test CASE-152."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["152", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.reports_browser import ReportsBrowserCase


class ReportsCase152(ReportsBrowserCase):
    def test_case_152_reports(self):
        report = self.generate_monthly_report()
        self.assertEqual(report.report_type, 'monthly')
        expect(self.page.get_by_role('heading', name='Generated Reports', exact=True)).to_be_visible()
        expect(self.generated_report_row(report)).to_be_visible()
        expect(self.page.get_by_role('dialog', name='Successfully Added!', exact=True)).to_be_visible()
