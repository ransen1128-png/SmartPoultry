"""Farm browser test CASE-046."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["46", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.farm_workflows_browser import FarmWorkflowCase


class FarmCase046(FarmWorkflowCase):
    def test_case_046_farm(self):
        self.sample_branch()
        self.open_farms()
        self.search_farms('No matching farm or branch')
        expect(self.page.locator('#branchList')).to_contain_text('No farms or branches match your search.')
        expect(self.page.locator('#branchList tr[data-branch-id]')).to_have_count(0)
