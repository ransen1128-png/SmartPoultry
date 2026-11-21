"""Farm browser test CASE-173."""

from playwright.sync_api import expect

from tools.farm_workflows_browser import FarmWorkflowCase


class FarmCase173(FarmWorkflowCase):
    def test_case_173_farm(self):
        self.sample_branch()
        self.open_farms()
        self.search_farms('No matching farm or branch')
        expect(self.page.locator('#branchList')).to_contain_text('No farms or branches match your search.')
        expect(self.page.locator('#branchList tr[data-branch-id]')).to_have_count(0)
