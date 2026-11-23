"""Revenue browser test CASE-111."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["111", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.revenue_browser import RevenueBrowserCase


class RevenueCase111(RevenueBrowserCase):
    def test_case_111_add_another_order_item(self):
        self.open_order()
        self.select_branch()
        expect(self.lines).to_have_count(1)
        self.modal.get_by_role('button', name='Add another item').click()
        expect(self.lines).to_have_count(2)
        second = self.lines.nth(1)
        expect(second.get_by_role('heading', name='Order item 2')).to_be_visible()
        for field in ('production', 'quantity', 'price_per_unit'):
            expect(second.locator(f'[name="{field}"]')).to_be_visible()
