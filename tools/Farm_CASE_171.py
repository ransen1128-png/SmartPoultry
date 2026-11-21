"""Farm browser test CASE-171."""

from playwright.sync_api import expect

from tools.farm_workflows_browser import FarmWorkflowCase


class FarmCase171(FarmWorkflowCase):
    def test_case_171_farm(self):
        self.sample_branch()
        self.open_farms()
        self.page.get_by_role('button', name=f'View {self.branch_name}', exact=True).click()
        dialog = self.page.get_by_role('dialog', name=self.branch_name, exact=True)
        expect(dialog.get_by_text(self.branch_address, exact=True)).to_be_visible()
