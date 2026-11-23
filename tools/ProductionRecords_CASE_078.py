"""Production Records browser test CASE-078."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["78", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.production_records_browser import ProductionRecordsBrowserCase


class ProductionRecordsCase078(ProductionRecordsBrowserCase):
    def test_case_078_branch_filters_flocks(self):
        self.open_add_form()
        self.page.locator('#id_branch').select_option(str(self.branch.pk))
        options = self.page.locator('#id_flock option:not([value=""])')
        expect(options).to_have_count(2)
        self.assertCountEqual(options.evaluate_all('options => options.map(option => option.value)'),
                              [str(self.layers.pk), str(self.broilers.pk)])
