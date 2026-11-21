"""Notifications browser test CASE-150."""

import re

from playwright.sync_api import expect

from tools.notifications_browser import NotificationsBrowserCase


class NotificationsCase150(NotificationsBrowserCase):
    def test_case_150_notifications(self):
        description = 'QA Sample Branch electricity bill'
        self.post_api('/api/expenses/', {
            'branch': self.branch.pk, 'expense_type': 'utilities', 'description': description,
            'amount': 350, 'date': self.today.isoformat(),
        })
        notification = self.notification('Successfully added utilities expense')
        expect(notification).to_contain_text(description)
        expect(notification).to_contain_text(re.compile(r'PHP 350(?:\.0+)?\b'))
