"""Verify that an assigned Flock ID cannot be edited, so it cannot be changed to a duplicate."""

import os
import unittest



try:
    from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser, live_base_url, read_test_value


BASE_URL = live_base_url()
FLOCKS_URL = f'{BASE_URL}/flocks/'


class LiveFlockTests(unittest.TestCase):
    def test_case_055_duplicate_flock_id_update(self):
        """CASE-055 | Flock ID cannot be edited & a duplicate ID sent on update is ignored."""
        email = os.environ.get('SMARTPOULTRY_TEST_EMAIL') or 'userx@gmail.com'
        password = read_test_value('SMARTPOULTRY_TEST_PASSWORD', 'Test account password: ', secret=True)

        browser = launch_browser()
        try:
            page = browser.new_page(locale='en-US')
            page.goto(f'{BASE_URL}/login/', timeout=90_000, wait_until='domcontentloaded')
            page.get_by_label('Email', exact=True).fill(email)
            page.get_by_label('Password', exact=True).fill(password)
            page.get_by_role('button', name='Login', exact=True).click()
            expect(page).to_have_url(f'{BASE_URL}/dashboard/', timeout=30_000)

            flock_id = read_test_value('SMARTPOULTRY_TEST_FLOCK_ID', 'Fixture flock ID: ')
            duplicate_id = read_test_value('SMARTPOULTRY_TEST_DUPLICATE_FLOCK_ID', 'Fixture flock ID: ')
            self.assertNotEqual(flock_id, duplicate_id)
            page.goto(FLOCKS_URL, timeout=90_000, wait_until='domcontentloaded')
            notification = page.locator('dialog#appDialog[open]')
            if notification.is_visible():
                notification.get_by_role('button', name='Close notification').click()
            expect(notification).to_be_hidden()

            row = page.locator('#flocksBody tr').filter(
                has=page.get_by_role('cell', name=flock_id, exact=True),
            )
            expect(row).to_have_count(1)
            row.get_by_role('button', name='Edit', exact=True).click()
            modal = page.locator('#addFlockModal')
            expect(modal.get_by_role('heading', name='Edit Flock', exact=True)).to_be_visible()
            identifier = modal.locator('[name="flock_id"]')
            expect(identifier).to_have_value(flock_id)
            self.assertTrue(identifier.evaluate('field => field.readOnly'), 'An assigned Flock ID must not be editable.')

            # Even a request that bypasses the form cannot change the assigned ID.
            records = page.request.get(f'{BASE_URL}/api/flocks/').json()['results']
            target = next(r for r in records if r['flock_id'] == flock_id)
            result = page.evaluate(
                """async ([url, duplicate]) => {
                    const token = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
                    const response = await fetch(url, {method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-CSRFToken': token},
                        body: JSON.stringify({flock_id: duplicate, correction_reason: 'CASE-055 duplicate ID attempt'})});
                    return {status: response.status, body: await response.json()};
                }""",
                [f"{BASE_URL}/api/flocks/{target['id']}/", duplicate_id],
            )
            self.assertEqual(result['status'], 200, result)
            self.assertEqual(result['body']['flock_id'], flock_id, 'The update changed the assigned Flock ID.')

            page.reload(wait_until='domcontentloaded')
            expect(row).to_have_count(1)
            print(f'Actual result: Flock ID {flock_id} is read-only and stayed {flock_id} after an update '
                  f'that sent {duplicate_id}.')
        finally:
            browser.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
