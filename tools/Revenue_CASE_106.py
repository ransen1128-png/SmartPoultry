"""Revenue browser test CASE-106."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["106", *sys.argv[1:]]))

from tools.revenue_browser import RevenueBrowserCase


class RevenueCase106(RevenueBrowserCase):
    def test_case_106_required_fields_block_sale(self):
        self.open_order()
        self.submit()
        self.assert_sale_blocked(
            self.modal.get_by_label('Buyer Name', exact=True),
            'valueMissing',
        )
