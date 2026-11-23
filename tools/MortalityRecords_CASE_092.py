"""Mortality Records browser test CASE-092."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["92", *sys.argv[1:]]))

from tools.automation_browser import expect

from production.models import MortalityRecord

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase092(MortalityRecordsBrowserCase):
    def test_case_092_accident_reduces_live_count_to_28(self):
        self.assertEqual(self.flock.quantity, 30)
        self.fill_add_form(quantity='2')
        self.page.locator('#id_reason').select_option('accident')
        self.submit()
        expect(self.page).to_have_url(self.records_url)

        record = MortalityRecord.objects.get(user=self.user)
        self.assertEqual((record.flock_id, record.quantity, record.reason), (self.flock.pk, 2, 'accident'))
        cells = self.record_row(record).get_by_role('cell')
        expect(cells.nth(3)).to_have_text('2')
        expect(cells.nth(4)).to_have_text('Accident')
        self.flock.refresh_from_db()
        self.assertEqual(self.flock.quantity, 28)
