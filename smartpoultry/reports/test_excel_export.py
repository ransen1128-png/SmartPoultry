from datetime import date
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.test import TestCase
from openpyxl import load_workbook

from expenses.models import Expense
from reports.models import Report
from revenue.models import Revenue

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class ExcelReportExportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='excel-owner')
        self.other = User.objects.create_user(username='excel-other')
        self.client.force_login(self.user)

    def report(self, kind, start, end):
        return Report.objects.create(user=self.user, report_type=kind, title=f'{kind} report', start_date=start, end_date=end)

    def workbook(self, report):
        response = self.client.get(f'/api/reports/{report.id}/download/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], XLSX)
        self.assertIn('.xlsx"', response['Content-Disposition'])
        return load_workbook(BytesIO(response.content))

    def column_a(self, sheet):
        return [cell.value for cell in sheet['A'] if isinstance(cell.value, str)]

    def test_weekly_report_has_daily_breakdown_and_formatted_record_sheets(self):
        Revenue.objects.create(user=self.user, revenue_type='eggs', quantity=Decimal('10'), unit='tray',
                               price_per_unit=Decimal('100'), date=date(2026, 11, 10), notes='=HYPERLINK("http://x","click")')
        Revenue.objects.create(user=self.other, revenue_type='eggs', quantity=Decimal('1'), unit='tray',
                               price_per_unit=Decimal('900'), date=date(2026, 11, 10), notes='Other sale')
        Expense.objects.create(user=self.user, expense_type='feed', description='Feed', amount=Decimal('300'), date=date(2026, 11, 9))
        wb = self.workbook(self.report('weekly', date(2026, 11, 8), date(2026, 11, 14)))

        self.assertEqual(wb.sheetnames, ['Summary', 'Revenue', 'Expenses', 'Production', 'Mortality', 'Flocks', 'Inventory'])
        summary = self.column_a(wb['Summary'])
        self.assertIn('Daily Breakdown', summary)
        self.assertEqual([label for label in summary if label[:4] in ('Sun,', 'Mon,', 'Tue,', 'Wed,', 'Thu,', 'Fri,', 'Sat,')],
                         ['Sun, Nov 08', 'Mon, Nov 09', 'Tue, Nov 10', 'Wed, Nov 11', 'Thu, Nov 12', 'Fri, Nov 13', 'Sat, Nov 14'])
        self.assertEqual(wb['Summary']['A8'].value, 1000)  # Total revenue card, owner only
        self.assertEqual(wb['Summary']['C8'].value, 700)   # Net profit card

        revenue = wb['Revenue']
        self.assertEqual(revenue['A2'].value.date(), date(2026, 11, 10))
        self.assertEqual(revenue['A2'].number_format, 'mmm d, yyyy')
        self.assertEqual(revenue.max_row, 3)  # header, one owner row, totals row
        self.assertEqual(revenue['H3'].value, '=SUBTOTAL(109,H2:H2)')
        notes = revenue['O2']
        self.assertEqual(notes.data_type, 's')  # user text is never a live formula
        self.assertEqual(revenue.freeze_panes, 'A2')
        self.assertIn('Revenue', revenue.tables)
        self.assertEqual(revenue['H3'].data_type, 'f')  # our own totals stay live formulas
        self.assertIsNone(revenue['G3'].value)  # unit prices are not totalled

    def test_breakdowns_add_up_records_sharing_a_day_and_branch(self):
        from core.models import Branch, Farm
        farm = Farm.objects.create(owner=self.user, name='Farm', location='Town', established_date=date(2026, 1, 1),
                                   contact_email='farm@example.com', contact_phone='09123456789')
        branch = Branch.objects.create(farm=farm, name='Labogon Branch')
        for price in ('7', '12', '180'):
            Revenue.objects.create(user=self.user, branch=branch, revenue_type='eggs', quantity=Decimal('10'),
                                   unit='tray', price_per_unit=Decimal(price), date=date(2026, 11, 14))
        sheet = self.workbook(self.report('weekly', date(2026, 11, 8), date(2026, 11, 14)))['Summary']
        rows = {sheet.cell(row=row, column=1).value: row for row in range(1, sheet.max_row + 1)}
        self.assertEqual(sheet.cell(row=rows['Sat, Nov 14'], column=2).value, 1990)
        self.assertEqual(sheet.cell(row=rows['Labogon Branch'], column=2).value, 1990)
        profit = sheet.cell(row=rows['Sat, Nov 14'], column=4)
        self.assertEqual((profit.data_type, profit.value), ('f', f"=B{rows['Sat, Nov 14']}-C{rows['Sat, Nov 14']}"))

    def test_breakdown_granularity_follows_report_type(self):
        cases = [
            ('daily', date(2026, 11, 14), date(2026, 11, 14), None, 0),
            ('monthly', date(2026, 11, 1), date(2026, 11, 30), 'Weekly Breakdown', 6),
            ('annual', date(2026, 1, 1), date(2026, 12, 31), 'Monthly Breakdown', 12),
        ]
        for kind, start, end, heading, periods in cases:
            with self.subTest(kind=kind):
                summary = self.column_a(self.workbook(self.report(kind, start, end))['Summary'])
                self.assertIn('By Branch', summary)
                for other in ('Daily Breakdown', 'Weekly Breakdown', 'Monthly Breakdown'):
                    (self.assertIn if other == heading else self.assertNotIn)(other, summary)
                if heading:
                    start_row = summary.index(heading)
                    rows = summary[start_row + 2:summary.index('Total', start_row)]
                    self.assertEqual(len(rows), periods)

    def test_empty_sheets_explain_there_are_no_records(self):
        wb = self.workbook(self.report('weekly', date(2026, 1, 5), date(2026, 1, 11)))
        self.assertEqual(wb['Mortality']['A2'].value, 'No records in this period.')
        self.assertEqual(wb['Flocks']['A2'].value, 'No flocks recorded.')
        self.assertEqual(wb['Inventory']['A2'].value, 'No inventory items recorded.')

    OTHER_MARKERS = ('OTHER-SALE', 'OTHER-EXPENSE', 'OTHER-PRODUCTION', 'OTHER-DEATH', 'OTHER-INVENTORY', 'OTHER-FLOCK')
    # Compared as cell values, not substrings: random order/transaction numbers can contain "777".
    OTHER_AMOUNTS = (777, 555, 999, 333, 11)

    def plant_other_user_data(self):
        """Give another user one record of every exported kind inside the report week, plus one owner sale."""
        from flocks.models import Flock
        from inventory.models import Inventory
        from production.models import MortalityRecord, ProductionRecord
        day = date(2026, 11, 10)
        flock = Flock.objects.create(user=self.other, flock_id='OTHER-FLOCK', breed='layers', quantity=999)
        Revenue.objects.create(user=self.other, revenue_type='eggs', quantity=Decimal('1'), unit='tray',
                               price_per_unit=Decimal('777'), date=day, notes='OTHER-SALE')
        Expense.objects.create(user=self.other, expense_type='feed', description='OTHER-EXPENSE', amount=Decimal('555'), date=day)
        ProductionRecord.objects.create(user=self.other, flock=flock, product_type='eggs', quantity=333, unit='pieces',
                                        date=day, notes='OTHER-PRODUCTION')
        MortalityRecord.objects.create(user=self.other, flock=flock, quantity=11, reason='disease', date=day, notes='OTHER-DEATH')
        Inventory.objects.create(user=self.other, item_type='feed', name='OTHER-INVENTORY', quantity=Decimal('5'),
                                 unit='kg', cost_per_unit=Decimal('10'))
        Revenue.objects.create(user=self.user, revenue_type='eggs', quantity=Decimal('2'), unit='tray',
                               price_per_unit=Decimal('50'), date=day, notes='MY-SALE')
        Revenue.objects.create(user=self.other, revenue_type='eggs', quantity=Decimal('1'), unit='tray',
                               price_per_unit=Decimal('777'), date=date(2026, 11, 3), notes='OTHER-SALE')
        return self.report('weekly', date(2026, 11, 8), date(2026, 11, 14))

    def test_workbook_never_contains_another_users_records(self):
        wb = self.workbook(self.plant_other_user_data())
        text = ' '.join(str(cell.value) for sheet in wb for row in sheet.iter_rows() for cell in row if cell.value is not None)
        self.assertIn('MY-SALE', text)
        for marker in self.OTHER_MARKERS:
            self.assertNotIn(marker, text)
        numbers = {cell.value for sheet in wb for row in sheet.iter_rows() for cell in row
                   if isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool)}
        for amount in self.OTHER_AMOUNTS:
            self.assertNotIn(amount, numbers)
        summary = wb['Summary']
        # Key figures: revenue, expenses, profit, eggs, mortality, active chicken are the owner's only.
        self.assertEqual([summary.cell(row=8, column=c).value for c in range(1, 7)], [100, 0, 100, 0, 0, 0])
        # The other user's sale in the prior week must not count as the owner's prior revenue.
        self.assertEqual(summary['A9'].value, 'New this period')

    def test_other_users_cannot_download_the_report(self):
        report = self.report('weekly', date(2026, 11, 8), date(2026, 11, 14))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/api/reports/{report.id}/download/').status_code, 404)

    def test_csv_export_is_removed(self):
        report = self.report('weekly', date(2026, 11, 8), date(2026, 11, 14))
        response = self.client.get(f'/api/reports/{report.id}/download/', {'export': 'csv'})
        self.assertEqual(response['Content-Type'], XLSX)

    def test_key_figures_compare_with_previous_period(self):
        for day, price, cost in ((date(2026, 11, 3), '80', '600'), (date(2026, 11, 10), '100', '300')):
            Revenue.objects.create(user=self.user, revenue_type='eggs', quantity=Decimal('10'), unit='tray',
                                   price_per_unit=Decimal(price), date=day)
            Expense.objects.create(user=self.user, expense_type='feed', description='Feed', amount=Decimal(cost), date=day)
        summary = self.workbook(self.report('weekly', date(2026, 11, 8), date(2026, 11, 14)))['Summary']
        self.assertEqual(summary['C7'].value, 'Net Profit · 70.0% margin')
        self.assertEqual([summary.cell(row=9, column=c).value for c in range(1, 7)],
                         ['▲ 25.0% vs prior', '▼ 50.0% vs prior', '▲ 250.0% vs prior', 'No prior data', 'No prior data', 'Current count'])
        # Lower expenses are good news: both revenue up and expenses down are green.
        self.assertEqual(summary['A9'].font.color.rgb[-6:], '1E7B34')
        self.assertEqual(summary['B9'].font.color.rgb[-6:], '1E7B34')
        self.assertEqual(summary['A10'].value, 'Compared with November 01, 2026 – November 07, 2026.')

    def test_previous_period_matches_calendar_for_month_quarter_and_year(self):
        from reports.excel_export import _previous_period
        cases = [
            ('weekly', date(2026, 11, 8), date(2026, 11, 14), date(2026, 11, 1), date(2026, 11, 7)),
            ('daily', date(2026, 11, 14), date(2026, 11, 14), date(2026, 11, 13), date(2026, 11, 13)),
            ('monthly', date(2026, 11, 1), date(2026, 11, 23), date(2026, 10, 1), date(2026, 10, 23)),
            ('monthly', date(2026, 11, 1), date(2026, 11, 30), date(2026, 10, 1), date(2026, 10, 31)),
            ('monthly', date(2026, 3, 1), date(2026, 3, 31), date(2026, 2, 1), date(2026, 2, 28)),
            ('quarterly', date(2026, 10, 1), date(2026, 12, 31), date(2026, 7, 1), date(2026, 9, 30)),
            ('annual', date(2026, 1, 1), date(2026, 11, 23), date(2025, 1, 1), date(2025, 11, 23)),
        ]
        for kind, start, end, previous_start, previous_end in cases:
            with self.subTest(kind=kind, start=start, end=end):
                report = Report(report_type=kind, start_date=start, end_date=end)
                self.assertEqual(_previous_period(report), (previous_start, previous_end))

    def test_summary_links_sheets_and_includes_type_tables_and_charts(self):
        Revenue.objects.create(user=self.user, revenue_type='eggs', quantity=Decimal('10'), unit='tray',
                               price_per_unit=Decimal('30'), date=date(2026, 11, 10))
        Revenue.objects.create(user=self.user, revenue_type='meat', quantity=Decimal('1'), unit='kg',
                               price_per_unit=Decimal('100'), date=date(2026, 11, 10))
        Expense.objects.create(user=self.user, expense_type='feed', description='Feed', amount=Decimal('300'), date=date(2026, 11, 9))
        report = self.report('weekly', date(2026, 11, 8), date(2026, 11, 14))
        content = self.client.get(f'/api/reports/{report.id}/download/').content
        summary = load_workbook(BytesIO(content))['Summary']
        self.assertEqual([summary.cell(row=4, column=c).hyperlink.location for c in range(1, 7)],
                         ["'Revenue'!A1", "'Expenses'!A1", "'Production'!A1", "'Mortality'!A1", "'Flocks'!A1", "'Inventory'!A1"])
        rows = {summary.cell(row=r, column=1).value: r for r in range(1, summary.max_row + 1)}
        top = rows['Revenue by Type']
        self.assertEqual([summary.cell(row=top + 2 + i, column=1).value for i in range(2)], ['Eggs', 'Meat'])
        self.assertEqual(summary.cell(row=top + 2, column=2).value, 300)
        self.assertEqual(summary.cell(row=top + 2, column=3).value, f'=IF($B${top + 4}=0,0,B{top + 2}/$B${top + 4})')
        with ZipFile(BytesIO(content)) as archive:
            charts = [archive.read(name).decode() for name in archive.namelist() if name.startswith('xl/charts/chart')]
        self.assertEqual(len(charts), 2)
        self.assertTrue(any('<barChart>' in chart for chart in charts))
        self.assertTrue(any('<pieChart>' in chart for chart in charts))

    def test_daily_report_charts_branches(self):
        from core.models import Branch, Farm
        farm = Farm.objects.create(owner=self.user, name='Farm', location='Town', established_date=date(2026, 1, 1),
                                   contact_email='farm@example.com', contact_phone='09123456789')
        branch = Branch.objects.create(farm=farm, name='North')
        Revenue.objects.create(user=self.user, branch=branch, revenue_type='eggs', quantity=Decimal('1'), unit='tray',
                               price_per_unit=Decimal('50'), date=date(2026, 11, 14))
        report = self.report('daily', date(2026, 11, 14), date(2026, 11, 14))
        with ZipFile(BytesIO(self.client.get(f'/api/reports/{report.id}/download/').content)) as archive:
            charts = [archive.read(name).decode() for name in archive.namelist() if name.startswith('xl/charts/chart')]
        self.assertEqual(len(charts), 1)
        self.assertIn('by Branch', charts[0])
