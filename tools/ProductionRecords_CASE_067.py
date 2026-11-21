"""Production Records browser test CASE-067."""

from playwright.sync_api import expect

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase067(ProductionRecordsBrowserCase):
    def test_case_067_branch_filters_flocks(self):
        self.open_add_form()
        self.page.locator('#id_branch').select_option(str(self.branch.pk))
        options = self.page.locator('#id_flock option:not([value=""])')
        expect(options).to_have_count(2)
        self.assertCountEqual(options.evaluate_all('options => options.map(option => option.value)'),
                              [str(self.layers.pk), str(self.broilers.pk)])
