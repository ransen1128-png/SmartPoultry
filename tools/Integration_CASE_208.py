"""SmartPoultry integration INT-024 (CASE-208)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['208', *sys.argv[1:]]))

from tools.notifications_browser import NotificationsBrowserCase
import Notifications_CASE_162 as workflow_1


class IntegrationCase208(NotificationsBrowserCase):
    def test_int_024(self):
        workflow_1.NotificationsCase162.test_case_162_notifications(self)
