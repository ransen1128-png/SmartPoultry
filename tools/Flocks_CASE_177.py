"""Flocks browser test CASE-177."""

from playwright.sync_api import expect

from tools.farm_workflows_browser import FlockWorkflowCase


class FlocksCase177(FlockWorkflowCase):
    def test_case_177_flocks(self):
        button = self.page.locator('#flockHistoryBtn')
        expect(button).to_have_text('History (0)')
        button.click()
        dialog = self.page.get_by_role('dialog', name='Flock History', exact=True)
        expect(dialog).to_be_visible()
        expect(dialog.get_by_text('No completed flocks yet.', exact=True)).to_be_visible()
