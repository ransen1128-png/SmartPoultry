"""Feedback browser test CASE-170."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["170", *sys.argv[1:]]))

from tools.automation_browser import expect


from tools.feedback_browser import FeedbackBrowserCase


class FeedbackCase170(FeedbackBrowserCase):
    def test_case_170_feedback(self):
        self.open_feedback()
        for field in ('Subject', 'Rating', 'Message'):
            expect(self.form.get_by_label(field, exact=True)).to_be_visible()
        rating = self.form.get_by_label('Rating', exact=True)
        expect(rating).to_have_value('5')
        expect(rating.locator('option:checked')).to_have_text('5 - Excellent')
