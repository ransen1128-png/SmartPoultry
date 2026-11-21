"""Farm browser test CASE-172."""

from playwright.sync_api import expect

from core.models import Branch
from tools.farm_workflows_browser import FarmWorkflowCase


class FarmCase172(FarmWorkflowCase):
    def test_case_172_farm(self):
        branch = self.sample_branch()
        Branch.objects.create(farm=self.farm, name='Different Test Branch', address='Different address')
        self.open_farms()
        expect(self.page.locator('#branchList tr[data-branch-id]')).to_have_count(2)
        self.search_farms(self.branch_name)
        row = self.page.locator('#branchList tr[data-branch-id]')
        expect(row).to_have_count(1)
        expect(row).to_have_attribute('data-branch-id', str(branch.pk))
        expect(row.get_by_role('cell', name=self.branch_name, exact=True)).to_be_visible()
