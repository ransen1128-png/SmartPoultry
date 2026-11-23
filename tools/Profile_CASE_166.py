"""Profile browser test CASE-166."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["166", *sys.argv[1:]]))

from playwright.sync_api import expect

from tools.profile_browser import ProfileBrowserCase


class ProfileCase166(ProfileBrowserCase):
    def test_case_166_profile(self):
        self.open_profile()
        for label in ('First Name', 'Last Name', 'Username', 'Email', 'Phone'):
            expect(self.profile_form.get_by_label(label, exact=True)).to_be_visible()
