"""Mortality Records browser test CASE-094."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["94", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase094(MortalityRecordsBrowserCase):
    def test_case_094_cancel_mortality_deletion(self):
        record = self.accident_fixture()
        self.page.goto(self.records_url)
        row = self.record_row(record)
        row.get_by_role('button', name='Delete').click()
        confirmation = self.page.locator('#appConfirmDialog')
        expect(confirmation.get_by_text('Delete this mortality record?', exact=True)).to_be_visible()
        confirmation.get_by_role('button', name='Cancel', exact=True).click()
        expect(confirmation).to_be_hidden()
        expect(row).to_be_visible()
        self.page.reload(wait_until='domcontentloaded')
        expect(row).to_be_visible()
        record.refresh_from_db()
        self.flock.refresh_from_db()
        self.assertEqual(record.quantity, 2)
        self.assertEqual(self.flock.quantity, 28)
