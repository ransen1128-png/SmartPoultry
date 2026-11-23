"""Feedback browser test CASE-168."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["168", *sys.argv[1:]]))

from tools.feedback_browser import FeedbackBrowserCase


class FeedbackCase168(FeedbackBrowserCase):
    def test_case_168_feedback(self):
        self.open_feedback()
        self.form.get_by_label('Message', exact=True).fill('QA feedback message.')
        self.assert_required_field_blocks_submission('Subject')
