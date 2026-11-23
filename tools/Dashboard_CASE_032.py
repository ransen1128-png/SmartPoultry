"""Verify that the deployed dashboard shows farm performance after login."""

import os
import re
import unittest

from playwright.sync_api import expect, sync_playwright

try:
    from tools.automation_browser import launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()


class LiveDashboardTests(unittest.TestCase):
    def test_case_032_dashboard_shows_farm_performance(self):
        """CASE-032 | Dashboard loads successfully & displays farm statistics, financial summaries, and charts."""
        email = os.environ.get('SMARTPOULTRY_TEST_EMAIL') or 'userx@gmail.com'
        password = read_test_value('SMARTPOULTRY_TEST_PASSWORD', 'Test account password: ', secret=True)

        with sync_playwright() as playwright:
            browser = launch_browser(playwright)
            try:
                page = browser.new_page(locale='en-US')
                page.goto(f'{BASE_URL}/login/', timeout=90_000, wait_until='domcontentloaded')
                page.get_by_label('Email', exact=True).fill(email)
                page.get_by_label('Password', exact=True).fill(password)
                page.get_by_role('button', name='Login', exact=True).click()

                expect(page).to_have_url(f'{BASE_URL}/dashboard/', timeout=30_000)
                expect(page.get_by_role('heading', name='Dashboard', exact=True)).to_be_visible()

                for label in ('Total Chicken', 'Mortality Rate', 'Production', 'Total Revenue', 'Total Expenses', 'Net Profit', 'Cash Flow'):
                    metric = page.locator('.metric-card').filter(has=page.get_by_text(label, exact=True))
                    expect(metric).to_be_visible()
                    expect(metric.locator('strong').first).to_have_text(re.compile(r'\d'))

                for chart_id in ('revenueChart', 'expensesChart', 'profitChart', 'feedChart'):
                    expect(page.locator(f'canvas#{chart_id}')).to_be_visible()
                    page.wait_for_function(
                        'id => Boolean(window.Chart?.getChart?.(id))', arg=chart_id, timeout=15_000,
                    )
                print('Actual result: Farm statistics, financial summaries, and four initialized charts are visible.')
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
