"""SmartPoultry integration INT-025 (CASE-209)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['209', *sys.argv[1:]]))

from tools.notifications_browser import NotificationsBrowserCase
import Notifications_CASE_163 as workflow_1


class IntegrationCase209(NotificationsBrowserCase):
    def test_int_025(self):
        workflow_1.NotificationsCase163.test_case_163_notifications(self)
