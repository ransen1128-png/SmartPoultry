"""SmartPoultry integration INT-005 (CASE-189)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['189', *sys.argv[1:]]))

from tools.revenue_browser import RevenueBrowserCase
import Revenue_CASE_115 as workflow_1
from revenue.models import Revenue


class IntegrationCase189(RevenueBrowserCase):
    def test_int_005(self):
        workflow_1.RevenueCase115.test_case_115_sales_reduce_available_production_stock(self)
        self.assertEqual(sum(sale.total_amount for sale in Revenue.objects.filter(user=self.user)), 332)
