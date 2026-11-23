"""Feedback browser test CASE-171."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["171", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.feedback_browser import FeedbackBrowserCase


class FeedbackCase171(FeedbackBrowserCase):
    def test_case_171_feedback(self):
        self.open_feedback()
        rating = self.form.get_by_label('Rating', exact=True)
        rating.select_option(label='4 - Good')
        expect(rating).to_have_value('4')
        expect(rating.locator('option:checked')).to_have_text('4 - Good')
