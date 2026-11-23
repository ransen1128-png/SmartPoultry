"""Flocks browser test CASE-067."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["67", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.farm_workflows_browser import FlockWorkflowCase


class FlocksCase067(FlockWorkflowCase):
    def test_case_067_flocks(self):
        modal = self.fill_flock('broilers')
        modal.get_by_label('Delivery / hatch date', exact=True).fill('2026-10-15')
        flock = self.save_new_flock(modal)
        self.assertEqual((flock['ready_from'], flock['readiness_window_end']), ('2026-11-09', '2026-12-14'))
        row = self.flock_row(flock['flock_id'])
        expect(row.get_by_role('cell', name='broilers', exact=True)).to_be_visible()
        expect(row.get_by_role('cell', name='2026-11-09 to 2026-12-14', exact=True)).to_be_visible()
