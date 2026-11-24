"""Run numbered browser cases from a checkout or an exported case folder."""

import argparse
import os
from pathlib import Path
import re
import sys
from types import ModuleType
import unittest


def main(argv=None):
    here = Path(__file__).resolve().parent
    cases_dir = here
    flat_export = (here / 'RENDER_SUITE.md').is_file()
    admin_render_cases = frozenset(range(177, 185)) | {185, 212}
    farm_render_cases = {166, 170, 171, 174, 175, 213}
    dual_target = admin_render_cases | farm_render_cases
    default_repo = here.parent if (here.parent / 'smartpoultry' / 'manage.py').is_file() else None
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cases', nargs='*', type=int, metavar='CASE')
    parser.add_argument(
        '--repo', type=Path,
        default=os.environ.get('SMARTPOULTRY_REPO') or default_repo,
        help='SmartPoultry checkout (also accepts SMARTPOULTRY_REPO)',
    )
    targets = parser.add_mutually_exclusive_group()
    targets.add_argument('--live', action='store_true', help='Run selected cases against Render')
    targets.add_argument('--local', action='store_true', help='Run cases with an isolated Django test database')
    parser.add_argument('--list', action='store_true', help='List case numbers and targets')
    args = parser.parse_args(argv)
    live = args.live or (flat_export and not args.local)

    cases = {}
    for path in sorted(cases_dir.glob('*_CASE_*.py')):
        number = int(re.search(r'_CASE_(\d+)$', path.stem)[1])
        if number in cases:
            parser.error(f'Duplicate case number {number:03}')
        uses_django_fixture = re.search(
            r'^from tools\.(?!automation_browser)\w+_browser import ',
            path.read_text(encoding='utf-8'),
            re.MULTILINE,
        )
        cases[number] = (path, uses_django_fixture is None)

    if not cases:
        parser.error(f'No numbered cases found in {cases_dir}.')

    if args.list:
        for number, (path, render_only) in sorted(cases.items()):
            target = 'Render' if render_only else 'Render + Local' if number in dual_target else 'Local fixture'
            print(f'{number:03}  {target:<14}  {path.stem}')
        return 0

    if live and not args.cases:
        parser.error('Select case numbers to run on Render. Use --list to see available cases.')
    selected = args.cases or [number for number, (_, live) in sorted(cases.items()) if not live]
    for number in selected:
        if number not in cases:
            parser.error(f'Unknown case {number:03}')
        if live and not cases[number][1] and number not in dual_target:
            parser.error(f'Case {number:03} requires an isolated test dataset and has no Render workflow.')
        if not live and cases[number][1]:
            parser.error(f'Case {number:03} requires --live.')

    sys.path.insert(0, str(cases_dir))
    labels = [cases[number][0].stem for number in selected]
    if flat_export:
        package = ModuleType('tools')
        package.__path__ = [str(cases_dir)]
        sys.modules['tools'] = package
    if live:
        for index, number in enumerate(selected):
            if number in admin_render_cases:
                admin_number = {185: 179, 212: 184}.get(number, number)
                labels[index] = f'tools.render_admin_operations.RenderAdminOperationsCase.test_case_{admin_number:03}'
            elif number in farm_render_cases:
                labels[index] = f'tools.render_farm_read_only.RenderFarmReadOnlyCase.test_case_{number:03}'
        suite = unittest.defaultTestLoader.loadTestsFromNames(labels)
        return int(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

    if args.repo is None or not (args.repo / 'smartpoultry' / 'manage.py').is_file():
        parser.error('Local cases need a SmartPoultry checkout. Pass --repo with its path.')
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo / 'smartpoultry'))
    sys.path.append(str(repo))
    # Keep the browser suite isolated from the application database and deployment config.
    os.environ.update(DJANGO_SETTINGS_MODULE='tools.automation_settings', DATABASE_URL='',
                      USE_POSTGRES='false', RENDER='', RENDER_EXTERNAL_HOSTNAME='')
    import django
    from django.test.runner import DiscoverRunner

    django.setup()
    return int(bool(DiscoverRunner(verbosity=2, interactive=False).run_tests(labels)))


if __name__ == '__main__':
    raise SystemExit(main())
