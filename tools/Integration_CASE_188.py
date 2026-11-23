"""SmartPoultry integration INT-004 (CASE-188)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['188', *sys.argv[1:]]))

from tools.mortality_records_browser import MortalityRecordsBrowserCase
import MortalityRecords_CASE_092 as workflow_1

from tools.automation_browser import expect

class IntegrationCase188(MortalityRecordsBrowserCase):
    def test_int_004(self):
        workflow_1.MortalityRecordsCase092.test_case_092_accident_reduces_live_count_to_28(self)
        self.page.goto(f"{self.live_server_url}/flocks/")
        row = self.page.locator("#flocksBody tr").filter(
            has=self.page.get_by_role("cell", name=self.flock.flock_id, exact=True),
        )
        expect(row.get_by_role("cell").nth(3)).to_have_text("28")
