"""SmartPoultry integration INT-009 (CASE-193)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['193', *sys.argv[1:]]))

from tools.mortality_records_browser import MortalityRecordsBrowserCase
import MortalityRecords_CASE_093 as workflow_1
from core.models import AuditEvent
from tools.change_history_browser import ChangeHistoryBrowserCase

# Use the same selectors for correction audit entries across fixtures.

from tools.automation_browser import expect

class IntegrationCase193(MortalityRecordsBrowserCase):
    event_card = ChangeHistoryBrowserCase.event_card

    def test_int_009(self):
        workflow_1.MortalityRecordsCase093.test_case_093_correction_reduces_live_count_to_27(self)
        event = AuditEvent.objects.get(owner=self.user, action='updated', object_type='production.MortalityRecord', reason='Corrected the test mortality count.')
        self.page.goto(f'{self.live_server_url}/change-history/')
        ChangeHistoryBrowserCase.assert_correction(self, event, '2', '3', 'Corrected the test mortality count.')
        self.page.goto(f"{self.live_server_url}/flocks/")
        row = self.page.locator("#flocksBody tr").filter(
            has=self.page.get_by_role("cell", name=self.flock.flock_id, exact=True),
        )
        expect(row.get_by_role("cell").nth(3)).to_have_text("27")
