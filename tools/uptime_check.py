"""Record whether the SmartPoultry site is up, and report the measured availability.

Start recording:  .venv\\Scripts\\python.exe tools\\uptime_check.py run
Show the result:  .venv\\Scripts\\python.exe tools\\uptime_check.py report

Keep the window open. A check is made every five minutes and added to uptime_log.csv.
When this computer's own internet is down the check is "unknown", not downtime, and
time when this computer is off is not measured. Regular checks also keep a sleeping
free Render service awake, so they do not measure its first-visit delay.
"""
import csv
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

URL = 'https://smartpoultry-l3qo.onrender.com/__health/'
CONTROL = 'https://www.gstatic.com/generate_204'
LOG = Path(__file__).resolve().parents[1] / 'uptime_log.csv'
EVERY = 300


def fetch(url, timeout):
    request = urllib.request.Request(url, headers={'User-Agent': 'uptime-check'})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, time.perf_counter() - started
    except urllib.error.HTTPError as error:
        return error.code, time.perf_counter() - started
    except (urllib.error.URLError, OSError):
        return None, time.perf_counter() - started


def check():
    status, seconds = fetch(URL, 90)
    if status == 200:
        return 'up', status, seconds
    if status is None and fetch(CONTROL, 20)[0] is None:
        return 'unknown', '', seconds
    return 'down', status or 'no response', seconds


def run():
    while True:
        began = time.monotonic()
        state, status, seconds = check()
        new = not LOG.exists()
        with LOG.open('a', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            if new:
                writer.writerow(['checked_at_utc', 'state', 'http_status', 'seconds'])
            stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
            writer.writerow([stamp, state, status, f'{seconds:.2f}'])
        print(stamp, state, status, f'{seconds:.2f}s', flush=True)
        time.sleep(max(1, EVERY - (time.monotonic() - began)))


def report():
    if not LOG.exists():
        raise SystemExit('No checks recorded yet.')
    with LOG.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    known = [row for row in rows if row['state'] in ('up', 'down')]
    if not known:
        raise SystemExit('No measured checks yet.')
    up = sum(row['state'] == 'up' for row in known)
    first, last = (datetime.fromisoformat(rows[i]['checked_at_utc']) for i in (0, -1))
    expected = int((last - first).total_seconds() // EVERY) + 1
    print(f'Period (UTC): {first} to {last}')
    print(f'Measured checks: {len(known)} (unknown: {len(rows) - len(known)})')
    print(f'Coverage of the period: {100 * min(1, len(known) / expected):.1f}%')
    print(f'Availability: {up} of {len(known)} checks = {100 * up / len(known):.2f}%')
    print('State the period, the number of checks and the coverage together with this figure.')


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) == 2 else ''
    if action == 'run':
        run()
    elif action == 'report':
        report()
    else:
        raise SystemExit(__doc__)
