"""SmartPoultry integration INT-006 (CASE-190)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['190', *sys.argv[1:]]))

from tools.feed_inventory_browser import FeedInventoryBrowserCase
import FeedInventory_CASE_103 as workflow_1
from expenses.models import Expense
from tools.automation_browser import expect


class IntegrationCase190(FeedInventoryBrowserCase):
    def test_int_006(self):
        workflow_1.FeedInventoryCase103.test_case_103_distribute_two_sacks(self)
        allocation = Expense.objects.get(user=self.user, branch=self.branch, inventory_distribution__isnull=False)
        self.assertEqual(allocation.amount, 2000)
        self.page.goto(f'{self.live_server_url}/expenses/')
        row = self.page.locator('#expensesBody tr').filter(has_text=allocation.description)
        expect(row.get_by_role('cell', name='₱2000.00', exact=True)).to_be_visible()
        expect(self.page.locator('#totalExpenses')).to_have_text('₱5000.00')
