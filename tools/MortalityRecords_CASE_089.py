"""Mortality Records browser test CASE-089."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["89", *sys.argv[1:]]))

from tools.automation_browser import expect

from production.models import MortalityRecord
from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase089(MortalityRecordsBrowserCase):
    def test_case_089_correction_reason_required(self):
        record = MortalityRecord.objects.create(
            user=self.user, branch=self.branch, flock=self.flock, quantity=2, date=self.today,
        )
        self.flock.refresh_from_db()
        saved_live_count = self.flock.quantity
        self.page.goto(self.records_url)
        edit_url = f'{self.records_url}{record.pk}/edit/'
        self.page.locator(f'a[href="/mortality-records/{record.pk}/edit/"]').click()
        expect(self.page).to_have_url(edit_url)
        self.page.locator('#id_quantity').fill('3')
        self.submit()
        self.assert_required('#correctionReason')
        expect(self.page).to_have_url(edit_url)
        record.refresh_from_db()
        self.flock.refresh_from_db()
        self.assertEqual(record.quantity, 2)
        self.assertEqual(self.flock.quantity, saved_live_count)
