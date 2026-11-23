"""Farm browser test CASE-044."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["44", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.farm_workflows_browser import FarmWorkflowCase


class FarmCase044(FarmWorkflowCase):
    def test_case_044_farm(self):
        self.sample_branch()
        self.open_farms()
        self.page.get_by_role('button', name=f'View {self.branch_name}', exact=True).click()
        dialog = self.page.get_by_role('dialog', name=self.branch_name, exact=True)
        expect(dialog.get_by_text(self.branch_address, exact=True)).to_be_visible()
