"""SmartPoultry integration INT-003 (CASE-187)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['187', *sys.argv[1:]]))

from tools.production_records_browser import ProductionRecordsBrowserCase
import ProductionRecords_CASE_080 as workflow_1

from tools.automation_browser import expect

class IntegrationCase187(ProductionRecordsBrowserCase):
    def test_int_003(self):
        workflow_1.ProductionRecordsCase080.test_case_080_record_five_meat_ready_chickens(self)
        self.page.goto(f"{self.live_server_url}/flocks/")
        row = self.page.locator("#flocksBody tr").filter(
            has=self.page.get_by_role("cell", name=self.broilers.flock_id, exact=True),
        )
        expect(row.get_by_role("cell").nth(3)).to_have_text("20")
