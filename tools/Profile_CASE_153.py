"""Profile browser test CASE-153."""

from tools.profile_browser import ProfileBrowserCase


class ProfileCase153(ProfileBrowserCase):
    def test_case_153_profile(self):
        message = self.assert_invalid_profile_field('Username', '', 'valueMissing')
        self.assertEqual(message, 'Please fill out this field.')
