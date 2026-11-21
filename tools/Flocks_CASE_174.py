"""Flocks browser test CASE-174."""

from playwright.sync_api import expect

from flocks.models import Flock
from tools.farm_workflows_browser import FlockWorkflowCase


class FlocksCase174(FlockWorkflowCase):
    def test_case_174_flocks(self):
        modal = self.fill_flock('broilers')
        date = modal.get_by_label('Delivery / hatch date', exact=True)
        expect(date).to_have_value('')
        modal.get_by_role('button', name='Save Flock', exact=True).click()
        self.assertTrue(date.evaluate('field => field.validity.valueMissing'))
        expect(date).to_have_accessible_description('Please fill out this field.')
        expect(modal.get_by_text('Please fill out this field.', exact=True)).to_be_visible()
        expect(modal).to_be_visible()
        self.assertFalse(Flock.objects.filter(user=self.user, breed='broilers').exists())
