"""Farm browser test CASE-045."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["45", *sys.argv[1:]]))

from playwright.sync_api import expect

from core.models import Branch
from tools.farm_workflows_browser import FarmWorkflowCase


class FarmCase045(FarmWorkflowCase):
    def test_case_045_farm(self):
        branch = self.sample_branch()
        Branch.objects.create(farm=self.farm, name='Different Test Branch', address='Different address')
        self.open_farms()
        expect(self.page.locator('#branchList tr[data-branch-id]')).to_have_count(2)
        self.search_farms(self.branch_name)
        row = self.page.locator('#branchList tr[data-branch-id]')
        expect(row).to_have_count(1)
        expect(row).to_have_attribute('data-branch-id', str(branch.pk))
        expect(row.get_by_role('cell', name=self.branch_name, exact=True)).to_be_visible()
