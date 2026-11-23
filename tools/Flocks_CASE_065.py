"""Flocks browser test CASE-065."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["65", *sys.argv[1:]]))

from playwright.sync_api import expect

from flocks.models import Flock
from tools.farm_workflows_browser import FlockWorkflowCase


class FlocksCase065(FlockWorkflowCase):
    def test_case_065_flocks(self):
        modal = self.fill_flock('broilers')
        date = modal.get_by_label('Delivery / hatch date', exact=True)
        expect(date).to_have_value('')
        modal.get_by_role('button', name='Save Flock', exact=True).click()
        self.assertTrue(date.evaluate('field => field.validity.valueMissing'))
        expect(date).to_have_accessible_description('Please fill out this field.')
        expect(modal.get_by_text('Please fill out this field.', exact=True)).to_be_visible()
        expect(modal).to_be_visible()
        self.assertFalse(Flock.objects.filter(user=self.user, breed='broilers').exists())
