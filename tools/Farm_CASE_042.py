"""Farm browser test CASE-042."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["42", *sys.argv[1:]]))

from playwright.sync_api import expect

from core.models import Branch, Farm
from tools.farm_workflows_browser import FarmWorkflowCase


class FarmCase042(FarmWorkflowCase):
    seed_farm = False

    def test_case_042_farm(self):
        self.open_farms()
        form = self.page.locator('main form').filter(has=self.page.get_by_role('button', name='Create Farm Profile'))
        for name, value in (
            ('farm_name', 'QA Farm'), ('farm_address', '125 QA Farm Road'),
            ('established_date', self.today.isoformat()), ('contact_email', 'farm@example.invalid'),
            ('contact_phone', '09123456789'),
        ):
            form.locator(f'[name="{name}"]').fill(value)
        form.get_by_role('button', name='Create Farm Profile').click()
        info = self.page.locator('[data-farm-information]')
        expect(info).to_be_visible()
        expect(self.page.get_by_role('heading', name='Farm Information', exact=True)).to_be_visible()
        for value in ('QA Farm', '125 QA Farm Road', 'farm@example.invalid', '09123456789'):
            expect(info.get_by_text(value, exact=True)).to_be_visible()
        expect(self.page.get_by_role('button', name='Add Branch', exact=True)).to_be_visible()
        self.assertEqual(Farm.objects.get(owner=self.user).name, 'QA Farm')
        self.assertFalse(Branch.objects.filter(farm__owner=self.user).exists())
