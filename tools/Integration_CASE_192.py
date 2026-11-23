"""SmartPoultry integration INT-008 (CASE-192)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['192', *sys.argv[1:]]))

from tools.revenue_browser import RevenueBrowserCase
import Revenue_CASE_114 as workflow_1


class IntegrationCase192(RevenueBrowserCase):
    def test_int_008(self):
        workflow_1.RevenueCase114.test_case_114_receipt_displays_both_items_and_order_total(self)
