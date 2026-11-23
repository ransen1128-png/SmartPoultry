"""Profile browser test CASE-164."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["164", *sys.argv[1:]]))

from tools.profile_browser import ProfileBrowserCase


class ProfileCase164(ProfileBrowserCase):
    def test_case_164_profile(self):
        message = self.assert_invalid_profile_field('Username', '', 'valueMissing')
        self.assertEqual(message, 'Please fill out this field.')
