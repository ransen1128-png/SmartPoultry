"""Feedback browser test CASE-169."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["169", *sys.argv[1:]]))

from tools.feedback_browser import FeedbackBrowserCase


class FeedbackCase169(FeedbackBrowserCase):
    def test_case_169_feedback(self):
        self.open_feedback()
        self.form.get_by_label('Subject', exact=True).fill('QA feedback subject')
        self.assert_required_field_blocks_submission('Message')
