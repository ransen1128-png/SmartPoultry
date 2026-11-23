"""Mortality Records browser test CASE-091."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["91", *sys.argv[1:]]))

from playwright.sync_api import expect
from core.models import Branch
from flocks.models import Flock

from tools.mortality_records_browser import MortalityRecordsBrowserCase


class MortalityRecordsCase091(MortalityRecordsBrowserCase):
    def test_case_091_sample_branch_lists_layer_and_broiler_flocks(self):
        broilers = Flock.objects.create(
            user=self.user, branch=self.branch, flock_id='02', breed='broilers',
            quantity=30, placement_date=self.today,
        )
        other_branch = Branch.objects.create(farm=self.branch.farm, name='Other Branch')
        Flock.objects.create(user=self.user, branch=other_branch, flock_id='03', breed='layers', quantity=30)

        self.open_add_form()
        flock = self.page.locator('#id_flock')
        expect(flock).to_be_disabled()
        self.page.locator('#id_branch').select_option(str(self.branch.pk))
        expect(flock).to_be_enabled()
        choices = flock.locator('option:not([value=""])')
        expect(choices).to_have_count(2)
        self.assertCountEqual(
            choices.evaluate_all('options => options.map(option => option.value)'),
            [str(self.flock.pk), str(broilers.pk)],
        )
