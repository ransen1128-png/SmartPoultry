"""SmartPoultry integration INT-010 (CASE-194)."""

import re
import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['194', *sys.argv[1:]]))

from tools.production_records_browser import ProductionRecordsBrowserCase
import ProductionRecords_CASE_081 as workflow_1
from core.models import AuditEvent
from tools.change_history_browser import ChangeHistoryBrowserCase

# Use the same selectors for correction audit entries across fixtures.


class IntegrationCase194(ProductionRecordsBrowserCase):
    event_card = ChangeHistoryBrowserCase.event_card

    def test_int_010(self):
        workflow_1.ProductionRecordsCase081.test_case_081_correct_egg_quantity(self)
        event = AuditEvent.objects.get(owner=self.layers.user, action='updated', object_type='production.ProductionRecord', reason='Corrected the test egg count.')
        self.page.goto(f'{self.live_server_url}/change-history/')
        ChangeHistoryBrowserCase.assert_correction(
            self, event, re.compile(r'^12(?:\.0+)?$'), re.compile(r'^14(?:\.0+)?$'),
            'Corrected the test egg count.',
        )
