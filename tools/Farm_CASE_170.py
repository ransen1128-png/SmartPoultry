"""Farm browser test CASE-170."""

from playwright.sync_api import expect

from tools.farm_workflows_browser import FarmWorkflowCase


class FarmCase170(FarmWorkflowCase):
    def test_case_170_farm(self):
        self.open_farms()
        expect(self.page.locator('[data-main-branch-label]')).to_have_count(0)
        self.page.get_by_role('button', name='Add Branch', exact=True).click()
        form = self.page.locator('#addBranchForm')
        form.get_by_label('Branch Name', exact=True).fill(self.branch_name)
        form.get_by_label('Address', exact=True).fill(self.branch_address)
        form.get_by_label('Contact Number', exact=True).fill('09123456789')
        form.get_by_role('button', name='Add Branch', exact=True).click()
        expect(self.page.locator('[data-farm-row] [data-main-branch-label]')).to_have_text('Main Branch')
        row = self.page.locator('#branchList tr[data-branch-id]')
        expect(row).to_have_count(1)
        expect(row.get_by_role('cell', name=self.branch_name, exact=True)).to_be_visible()
        self.assertEqual(self.farm.branches.get().address, self.branch_address)
