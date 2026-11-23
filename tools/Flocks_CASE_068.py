"""Flocks browser test CASE-068."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["68", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.farm_workflows_browser import FlockWorkflowCase


class FlocksCase068(FlockWorkflowCase):
    def test_case_068_flocks(self):
        button = self.page.locator('#flockHistoryBtn')
        expect(button).to_have_text('History (0)')
        button.click()
        dialog = self.page.get_by_role('dialog', name='Flock History', exact=True)
        expect(dialog).to_be_visible()
        expect(dialog.get_by_text('No completed flocks yet.', exact=True)).to_be_visible()
