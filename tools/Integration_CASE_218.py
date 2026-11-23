"""SmartPoultry integration INT-034 (CASE-218)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['218', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.revenue_browser import RevenueBrowserCase


class IntegrationCase218(RevenueBrowserCase):
    def test_int_034(self):
        self.open_order()
        self.fill_order_header()
        self.fill_line(0, self.eggs, '14', '8')
        with self.page.expect_response(
            lambda response: response.url.endswith('/api/revenue/order/') and response.request.method == 'POST',
        ) as sale:
            self.submit()
        self.assertEqual(sale.value.status, 201)
        self.page.goto(f'{self.live_server_url}/production-records/')
        self.page.get_by_role('button', name='History (1)', exact=True).click()
        row = self.page.locator(f'#productionHistoryTable tr[data-production-id="{self.eggs.pk}"]')
        expect(row).to_be_visible()
        expect(row.get_by_role('cell').last).to_have_text('0')
