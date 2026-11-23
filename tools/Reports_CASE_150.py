"""Reports browser test CASE-150."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["150", *sys.argv[1:]]))

from tools.automation_browser import expect

import re


from tools.reports_browser import ReportsBrowserCase


class ReportsCase150(ReportsBrowserCase):
    def test_case_150_reports(self):
        self.assertTrue(self.apply_expense_filter(self.branch.name).ok)
        self.page.get_by_role('tab', name='Feed Distribution', exact=True).click()
        expect(self.page.get_by_role('tabpanel', name='Feed Distribution', exact=True)).to_be_visible()
        row = self.page.locator('#feedUsageBody tr').filter(
            has=self.page.get_by_role('cell', name=self.branch.name, exact=True),
        )
        expect(row).to_have_count(1)
        cells = row.get_by_role('cell')
        expect(cells.nth(1)).to_contain_text('flock not recorded')
        expect(cells.nth(2)).to_have_text(re.compile(r'^50(?:\.0+)? kg$'))
        expect(cells.nth(3)).to_have_text('\u20b12000.00')
        expect(cells.nth(5)).to_have_text('Not available')
