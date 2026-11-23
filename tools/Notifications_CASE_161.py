"""Notifications browser test CASE-161."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["161", *sys.argv[1:]]))

from tools.automation_browser import expect

import re


from tools.notifications_browser import NotificationsBrowserCase


class NotificationsCase161(NotificationsBrowserCase):
    def test_case_161_notifications(self):
        description = 'QA Sample Branch electricity bill'
        self.post_api('/api/expenses/', {
            'branch': self.branch.pk, 'expense_type': 'utilities', 'description': description,
            'amount': 350, 'date': self.today.isoformat(),
        })
        notification = self.notification('Successfully added utilities expense')
        expect(notification).to_contain_text(description)
        expect(notification).to_contain_text(re.compile(r'PHP 350(?:\.0+)?\b'))
