"""Measure mobile overflow in Chrome with an isolated local owner session."""

import argparse
import json
import os
from pathlib import Path
import sys

try:
    from tools.automation_browser import expect, launch_browser
    from tools.selenium_audit import capture_page, emulate_viewport, open_owner_session
except ModuleNotFoundError:
    from automation_browser import expect, launch_browser
    from selenium_audit import capture_page, emulate_viewport, open_owner_session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'smartpoultry'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django

django.setup()

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore


PATHS = (
    'dashboard/', 'farm/branches/', 'flocks/', 'production-records/',
    'production-records/add/', 'mortality-records/', 'mortality-records/add/',
    'inventory/', 'revenue/', 'expenses/', 'settings/', 'reports/', 'rooster-age-estimator/',
)
DIALOGS = {'inventory/': '#addInventoryModal', 'revenue/': '#addRevenueModal', 'expenses/': '#addExpenseModal'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--width', type=int, default=390)
    width_limit = parser.parse_args().width
    out = ROOT / f'.postgres-migration/mobile-audit-{width_limit}'
    out.mkdir(parents=True, exist_ok=True)
    session = SessionStore()
    browser = launch_browser()
    results = []
    try:
        page = browser.new_page()
        emulate_viewport(page, width_limit, 844, mobile=True)
        open_owner_session(page, session, get_user_model().objects.get(pk=3))
        for path in PATHS:
            response = page.goto(f'http://127.0.0.1:8000/{path}')
            if response is None:
                raise RuntimeError(f'No HTTP response was captured for {path}')
            item = page.evaluate("""
                limit => ({
                    viewport: innerWidth,
                    width: document.documentElement.scrollWidth,
                    overflow: [...document.querySelectorAll('body *')]
                        .filter(el => el.getBoundingClientRect().right > limit + 2 &&
                            !el.closest('.table-responsive') && getComputedStyle(el).position !== 'absolute')
                        .slice(0, 12).map(el => ({tag: el.tagName, cls: el.className}))
                })
            """, width_limit)
            item.update(path=path, http=response.status, requested_width=width_limit,
                        fits_screen=item['width'] <= width_limit + 2)
            results.append(item)
            if response.ok:
                capture_page(page, out / (path.replace('/', '_') + '.png'))
            if target := DIALOGS.get(path):
                page.locator(f'[data-bs-target="{target}"]').click()
                expect(page.locator(target)).to_be_visible()
                results.append(check_width(page, path + ' add dialog', width_limit))
            if path == 'settings/':
                page.locator('#security-tab').click()
                expect(page.locator('#security-panel')).to_be_visible()
                results.append(check_width(page, path + ' security', width_limit))
    finally:
        try:
            browser.close()
        finally:
            if session.session_key:
                session.delete()
    report = json.dumps(results, indent=2)
    (out / 'report.json').write_text(report, encoding='utf-8')
    print(report)


def check_width(page, path, width_limit):
    width = page.evaluate('() => document.documentElement.scrollWidth')
    return {'path': path, 'requested_width': width_limit, 'width': width, 'fits_screen': width <= width_limit + 2}


if __name__ == '__main__':
    main()
