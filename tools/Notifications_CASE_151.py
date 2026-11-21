"""Notifications browser test CASE-151."""

import re

from playwright.sync_api import expect

from tools.notifications_browser import NotificationsBrowserCase


class NotificationsCase151(NotificationsBrowserCase):
    def test_case_151_notifications(self):
        response = self.client.post('/mortality-records/add/', {
            'branch': self.branch.pk, 'flock': self.flock.pk, 'quantity': 2,
            'reason': 'accident', 'date': self.today.isoformat(),
        })
        self.assertRedirects(response, '/mortality-records/', fetch_redirect_response=False)
        notification = self.notification('Successfully added mortality record')
        expect(notification).to_contain_text(re.compile(r'Recorded 2 mortality for flock 01 due to accident\.', re.I))
