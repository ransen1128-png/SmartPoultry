"""Revenue browser test CASE-099."""

from playwright.sync_api import expect

from tools.revenue_browser import RevenueBrowserCase


class RevenueCase099(RevenueBrowserCase):
    def test_case_099_sample_branch_lists_eggs_and_meat_ready(self):
        self.open_order()
        self.select_branch()
        options = self.lines.first.locator('[name="production"] option:not([value=""])')
        expect(options).to_have_count(2)
        expect(options.and_(self.page.locator(f'option[value="{self.eggs.pk}"]'))).to_contain_text('Eggs (Medium)')
        expect(options.and_(self.page.locator(f'option[value="{self.meat.pk}"]'))).to_contain_text('Meat Ready')
