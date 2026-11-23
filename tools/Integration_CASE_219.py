"""SmartPoultry integration INT-035 (CASE-219)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['219', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.feed_inventory_browser import FeedInventoryBrowserCase
from expenses.models import Expense


class IntegrationCase219(FeedInventoryBrowserCase):
    def test_int_035(self):
        lot = self.distribution_fixture()
        self.open_inventory()
        self.page.locator('#allDistributionHistoryBtn').click()
        row = self.page.locator('#distributionHistoryBody tr').filter(has_text=self.branch.name)
        row.get_by_role('button', name='Reverse', exact=True).click()
        modal = self.page.locator('#reverseDistributionModal')
        modal.get_by_label('Reason', exact=True).fill('Reversed unused integration fixture.')
        with self.page.expect_response(
            lambda response: response.url.endswith(f'/distributions/{lot.pk}/reverse/')
            and response.request.method == 'POST',
        ) as reversal:
            modal.get_by_role('button', name='Reverse distribution', exact=True).click()
        self.assertTrue(reversal.value.ok, reversal.value.text())
        self.page.reload()
        self.assert_stock(lot.inventory, 5)
        self.page.goto(f'{self.live_server_url}/expenses/')
        self.assertFalse(Expense.objects.filter(inventory_distribution=lot, amount__gt=0).exists())
        expect(self.page.locator('#totalExpenses')).to_have_text('₱5000.00')
