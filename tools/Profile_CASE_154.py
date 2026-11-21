"""Profile browser test CASE-154."""

from tools.profile_browser import ProfileBrowserCase


class ProfileCase154(ProfileBrowserCase):
    def test_case_154_profile(self):
        message = self.assert_invalid_profile_field('Email', 'invalid-email.example', 'typeMismatch')
        self.assertIn('@', message)
