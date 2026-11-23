"""SmartPoultry integration INT-038 (CASE-222)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['222', *sys.argv[1:]]))

from tools.feed_inventory_browser import FeedInventoryBrowserCase


class IntegrationCase222(FeedInventoryBrowserCase):
    def test_int_038(self):
        self.skipTest(
            'The checkout has no Backup & Evaluation browser route. '
            'An isolated PostgreSQL backup scheduler, restore target, and status page are required.'
        )
