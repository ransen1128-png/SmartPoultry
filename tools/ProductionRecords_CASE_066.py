"""Production Records browser test CASE-066."""

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase066(ProductionRecordsBrowserCase):
    def test_case_066_edit_without_correction_reason(self):
        record = self.egg_fixture()
        self.open_egg_edit(record)
        self.page.locator('#id_quantity').fill('14')
        self.submit()
        self.assert_required('#correctionReason')
        record.refresh_from_db()
        self.assertEqual(record.quantity, 12)
