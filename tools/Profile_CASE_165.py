"""Profile browser test CASE-165."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["165", *sys.argv[1:]]))

from tools.profile_browser import ProfileBrowserCase


class ProfileCase165(ProfileBrowserCase):
    def test_case_165_profile(self):
        message = self.assert_invalid_profile_field('Email', 'invalid-email.example', 'typeMismatch')
        self.assertIn('@', message)
