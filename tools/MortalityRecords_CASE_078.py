"""Mortality Records browser test CASE-078."""

from playwright.sync_api import expect
from production.models import MortalityRecord
from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase078(MortalityRecordsBrowserCase):
    def test_case_078_correction_reason_required(self):
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
        self.assert_required('#correctionReason', 'Please fill out this field.')
        expect(self.page).to_have_url(edit_url)
        record.refresh_from_db()
        self.flock.refresh_from_db()
        self.assertEqual(record.quantity, 2)
        self.assertEqual(self.flock.quantity, saved_live_count)
