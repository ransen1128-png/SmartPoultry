"""Revenue browser test CASE-110."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["110", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.revenue_browser import RevenueBrowserCase


class RevenueCase110(RevenueBrowserCase):
    def test_case_110_sample_branch_lists_eggs_and_meat_ready(self):
        self.open_order()
        self.select_branch()
        options = self.lines.first.locator('[name="production"] option:not([value=""])')
        expect(options).to_have_count(2)
        expect(options.and_(self.page.locator(f'option[value="{self.eggs.pk}"]'))).to_contain_text('Eggs (Medium)')
        expect(options.and_(self.page.locator(f'option[value="{self.meat.pk}"]'))).to_contain_text('Meat Ready')
