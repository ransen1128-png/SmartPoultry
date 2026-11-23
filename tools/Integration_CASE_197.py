"""SmartPoultry integration INT-013 (CASE-197)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['197', *sys.argv[1:]]))

from tools.farm_workflows_browser import DashboardWorkflowCase
from tools.automation_browser import expect
from datetime import timedelta

from flocks.models import Flock
from production.models import ProductionRecord


class IntegrationCase197(DashboardWorkflowCase):
    def test_int_013(self):
        self.flock.quantity = 27
        self.flock.save(update_fields=['quantity'])
        broilers = Flock.objects.create(
            user=self.user, branch=self.branch, flock_id='02', breed='broilers',
            quantity=25, placement_date=self.today - timedelta(days=30),
        )
        ProductionRecord.objects.create(
            user=self.user, branch=self.branch, flock=broilers, product_type='meat_ready',
            quantity=5, date=self.today,
        )
        self.apply_dashboard(11)
        self.expect_metric('Total Chicken', '47')
        expect(self.page.locator('#dashboardProduction strong')).to_have_text(['14', '5'])
