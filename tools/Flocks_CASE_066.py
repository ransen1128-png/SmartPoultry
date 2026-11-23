"""Flocks browser test CASE-066."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["66", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.farm_workflows_browser import FlockWorkflowCase


class FlocksCase066(FlockWorkflowCase):
    def test_case_066_flocks(self):
        flock = self.save_new_flock(self.fill_flock('layers'))
        self.page.reload(wait_until='domcontentloaded')
        row = self.flock_row(flock['flock_id'])
        expect(row).to_have_count(1)
        for value in (self.branch.name, 'layers', '30', 'active'):
            expect(row.get_by_role('cell', name=value, exact=True)).to_be_visible()
