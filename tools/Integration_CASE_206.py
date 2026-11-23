"""SmartPoultry integration INT-022 (CASE-206)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['206', *sys.argv[1:]]))

from tools.notifications_browser import NotificationsBrowserCase
import Notifications_CASE_161 as workflow_1


class IntegrationCase206(NotificationsBrowserCase):
    def test_int_022(self):
        workflow_1.NotificationsCase161.test_case_161_notifications(self)
