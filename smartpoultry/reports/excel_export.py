"""Formatted Excel workbook for a saved report.

Layout:
  Summary     title block, key figures, a period breakdown sized to the report
              type (daily: by branch, weekly: by day, monthly: by week,
              quarterly/annual: by month) and a by-branch breakdown.
  Revenue, Expenses, Production, Mortality
              records in the report period as filterable Excel tables with a
              SUBTOTAL row that follows the active filter.
  Flocks, Inventory
              current snapshot at export time.
"""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.db.models import Sum
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

BRAND = '1F6F43'
BRAND_LIGHT = 'E8F3EC'
MUTED = '6B7280'
PESO = '"₱"#,##0.00;[Red]-"₱"#,##0.00'
QTY = '#,##0.00'
COUNT = '#,##0'
DATE = 'mmm d, yyyy'
THIN = Side(style='thin', color='D1D5DB')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEADER_FILL = PatternFill('solid', fgColor=BRAND)
HEADER_FONT = Font(bold=True, color='FFFFFF')
TOTAL_FILL = PatternFill('solid', fgColor=BRAND_LIGHT)
FORMATS = {'money': PESO, 'rate': PESO, 'qty': QTY, 'count': COUNT, 'date': DATE}


def report_records(report):
    """Owner-scoped records for the report period, shared by the CSV and Excel exports."""
    from expenses.models import Expense
    from flocks.models import Flock
    from inventory.models import Inventory
    from production.models import MortalityRecord, ProductionRecord
    from revenue.models import Revenue

    period = {'user': report.user, 'date__gte': report.start_date, 'date__lte': report.end_date}
    return {
        'revenue': Revenue.objects.filter(**period).select_related('flock', 'branch', 'production').order_by('date', 'created_at'),
        'expenses': Expense.objects.filter(**period).select_related('branch').order_by('date', 'created_at'),
        'production': ProductionRecord.objects.filter(**period).select_related('flock', 'branch').order_by('date', 'created_at'),
        'mortality': MortalityRecord.objects.filter(**period).select_related('flock', 'branch').order_by('date', 'created_at'),
        'inventory': Inventory.objects.filter(user=report.user).order_by('item_type', 'name'),
        'flocks': Flock.objects.filter(user=report.user).select_related('branch').order_by('branch__name', 'flock_id'),
    }


def _put(ws, row, column, value, number_format=None, formula=False):
    cell = ws.cell(row=row, column=column, value=value)
    # openpyxl turns any string starting with '=' into a formula; user-entered
    # text (notes, buyer names) must never execute in the recipient's Excel.
    # Only formulas this module builds itself pass formula=True.
    if not formula and isinstance(value, str) and value.startswith('='):
        cell.data_type = 's'
    if number_format:
        cell.number_format = number_format
    return cell


def _period_unit(report):
    span = (report.end_date - report.start_date).days + 1
    kind = report.report_type
    if kind == 'daily' or span == 1:
        return None
    if kind == 'weekly' or (kind not in ('monthly', 'quarterly', 'annual') and span <= 14):
        return 'day'
    if kind == 'monthly' or (kind not in ('quarterly', 'annual') and span <= 62):
        return 'week'
    return 'month'


def _periods(report, unit):
    """Yield (label, first_day, last_day) covering the report range exactly."""
    start, end = report.start_date, report.end_date
    if unit == 'day':
        day = start
        while day <= end:
            yield day.strftime('%a, %b %d'), day, day
            day += timedelta(days=1)
    elif unit == 'week':
        first, number = start, 1
        while first <= end:
            last = min(first + timedelta(days=6 - first.weekday()), end)  # weeks end on Sunday
            yield f"Week {number} ({first:%b %d} – {last:%b %d})", first, last
            first, number = last + timedelta(days=1), number + 1
    else:
        first = start
        while first <= end:
            following = first.replace(year=first.year + 1, month=1, day=1) if first.month == 12 else first.replace(month=first.month + 1, day=1)
            last = min(following - timedelta(days=1), end)
            yield first.strftime('%B %Y'), first, last
            first = following


def _daily_totals(queryset, field, **filters):
    # order_by() clears the record ordering; otherwise Django adds the ordering
    # columns (created_at) to GROUP BY and returns one row per record.
    rows = queryset.filter(**filters).order_by().values('date').annotate(total=Sum(field))
    return {row['date']: row['total'] or 0 for row in rows}


def _branch_totals(queryset, field, **filters):
    rows = queryset.filter(**filters).order_by().values('branch__name').annotate(total=Sum(field))
    return {row['branch__name'] or 'Unassigned': row['total'] or 0 for row in rows}


def _breakdown(ws, row, title, labels, series):
    """Write a Period | Revenue | Expenses | Profit | Eggs | Mortality table with live formulas."""
    ws.cell(row=row, column=1, value=title).font = Font(bold=True, size=12, color=BRAND)
    row += 1
    headers = ['Period' if title != 'By Branch' else 'Branch', 'Revenue', 'Expenses', 'Profit', 'Eggs Produced', 'Mortality']
    for column, header in enumerate(headers, 1):
        cell = ws.cell(row=row, column=column, value=header)
        cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BOX
        cell.alignment = Alignment(horizontal='center' if column > 1 else 'left')
    first = row + 1
    for label, (revenue, expenses, eggs, deaths) in zip(labels, series):
        row += 1
        _put(ws, row, 1, label)
        _put(ws, row, 2, revenue, PESO)
        _put(ws, row, 3, expenses, PESO)
        _put(ws, row, 4, f'=B{row}-C{row}', PESO, formula=True)
        _put(ws, row, 5, eggs, COUNT)
        _put(ws, row, 6, deaths, COUNT)
        for column in range(1, 7):
            ws.cell(row=row, column=column).border = BOX
    if row >= first:
        row += 1
        _put(ws, row, 1, 'Total')
        for column, (letter, fmt) in enumerate(zip('BCDEF', (PESO, PESO, PESO, COUNT, COUNT)), 2):
            _put(ws, row, column, f'=SUM({letter}{first}:{letter}{row - 1})', fmt, formula=True)
        for column in range(1, 7):
            cell = ws.cell(row=row, column=column)
            cell.font, cell.fill, cell.border = Font(bold=True), TOTAL_FILL, BOX
    else:
        row += 1
        _put(ws, row, 1, 'No records in this period.').font = Font(italic=True, color=MUTED)
    return row + 2


def _summary_sheet(wb, report, records):
    ws = wb.active
    ws.title = 'Summary'
    ws.sheet_properties.tabColor = BRAND
    revenue, expenses, production, mortality = (records[key] for key in ('revenue', 'expenses', 'production', 'mortality'))
    money_in = revenue.aggregate(t=Sum('total_amount'))['t'] or 0
    money_out = expenses.aggregate(t=Sum('amount'))['t'] or 0
    figures = [
        ('Total Revenue', money_in, PESO),
        ('Total Expenses', money_out, PESO),
        ('Net Profit', money_in - money_out, PESO),
        ('Eggs Produced', production.filter(product_type='eggs').aggregate(t=Sum('quantity'))['t'] or 0, COUNT),
        ('Mortality', mortality.aggregate(t=Sum('quantity'))['t'] or 0, COUNT),
        ('Active Chicken (now)', records['flocks'].filter(status='active').aggregate(t=Sum('quantity'))['t'] or 0, COUNT),
    ]

    ws.merge_cells('A1:F1')
    title = ws['A1']
    title.value = f'SMARTPOULTRY · {report.get_report_type_display()}'
    title.font = Font(bold=True, size=18, color='FFFFFF')
    title.fill = HEADER_FILL
    title.alignment = Alignment(vertical='center', indent=1)
    ws.row_dimensions[1].height = 34
    ws.merge_cells('A2:F2')
    period = (f'{report.start_date:%B %d, %Y}' if report.start_date == report.end_date
              else f'{report.start_date:%B %d, %Y} – {report.end_date:%B %d, %Y}')
    ws['A2'] = f'{report.title}  ·  {period}'
    ws['A2'].font = Font(bold=True, size=12)
    ws.merge_cells('A3:F3')
    generated = timezone.localtime(report.generated_at)
    ws['A3'] = f'Prepared for {report.user.username}  ·  Generated {generated:%b %d, %Y %I:%M %p} {generated.tzname()}'
    ws['A3'].font = Font(italic=True, color=MUTED)

    ws['A5'] = 'Key Figures'
    ws['A5'].font = Font(bold=True, size=12, color=BRAND)
    for column, (label, value, fmt) in enumerate(figures, 1):
        head = ws.cell(row=6, column=column, value=label)
        head.font, head.fill, head.border = Font(bold=True, color=MUTED, size=9), TOTAL_FILL, BOX
        head.alignment = Alignment(horizontal='center')
        cell = _put(ws, 7, column, value, fmt)
        cell.font, cell.border = Font(bold=True, size=14), BOX
        cell.alignment = Alignment(horizontal='center')
    ws.row_dimensions[7].height = 26

    row = 9
    unit = _period_unit(report)
    if unit:
        daily = (_daily_totals(revenue, 'total_amount'), _daily_totals(expenses, 'amount'),
                 _daily_totals(production, 'quantity', product_type='eggs'), _daily_totals(mortality, 'quantity'))
        labels, series = [], []
        for label, first, last in _periods(report, unit):
            days = [first + timedelta(days=offset) for offset in range((last - first).days + 1)]
            labels.append(label)
            series.append(tuple(sum((source.get(day, 0) for day in days), Decimal(0)) for source in daily))
        title = {'day': 'Daily Breakdown', 'week': 'Weekly Breakdown', 'month': 'Monthly Breakdown'}[unit]
        row = _breakdown(ws, row, title, labels, series)

    by_branch = [_branch_totals(revenue, 'total_amount'), _branch_totals(expenses, 'amount'),
                 _branch_totals(production, 'quantity', product_type='eggs'), _branch_totals(mortality, 'quantity')]
    branches = sorted(set().union(*by_branch), key=lambda name: (name == 'Unassigned', name.lower()))
    row = _breakdown(ws, row, 'By Branch', branches, [tuple(source.get(name, 0) for source in by_branch) for name in branches])

    _put(ws, row, 1, 'Flocks and Inventory sheets show current status at export time; all other figures cover the report period.').font = Font(italic=True, color=MUTED, size=9)
    ws.column_dimensions['A'].width = 34
    for letter in 'BCDEF':
        ws.column_dimensions[letter].width = 18
    ws.sheet_view.showGridLines = False
    _print_setup(ws, report)


def _data_sheet(wb, report, title, columns, rows, color):
    """columns: [(header, kind)] where kind is text/date/money/rate/qty/count.

    money/qty/count get a SUBTOTAL total that follows the active filter; rate
    (unit prices) is formatted as money but never totalled.
    """
    ws = wb.create_sheet(title)
    ws.sheet_properties.tabColor = color
    for column, (header, _) in enumerate(columns, 1):
        cell = ws.cell(row=1, column=column, value=header)
        cell.font = Font(bold=True)
    widths = [len(header) + 4 for header, _ in columns]
    for row_number, values in enumerate(rows, 2):
        for column, ((_, kind), value) in enumerate(zip(columns, values), 1):
            if value is None:
                value = ''
            _put(ws, row_number, column, value, FORMATS.get(kind))
            widths[column - 1] = max(widths[column - 1], 14 if kind == 'date' else len(str(value)) + 2)
    last_column = get_column_letter(len(columns))
    if rows:
        last_row = len(rows) + 1
        table = Table(displayName=title.replace(' ', ''), ref=f'A1:{last_column}{last_row}')
        table.tableStyleInfo = TableStyleInfo(name='TableStyleMedium7', showRowStripes=True)
        ws.add_table(table)
        total_row = last_row + 1
        _put(ws, total_row, 1, 'Total (visible rows)').font = Font(bold=True)
        for column, (_, kind) in enumerate(columns, 1):
            if kind in ('money', 'qty', 'count') and column > 1:
                letter = get_column_letter(column)
                cell = _put(ws, total_row, column, f'=SUBTOTAL(109,{letter}2:{letter}{last_row})', FORMATS[kind], formula=True)
                cell.font = Font(bold=True)
        for column in range(1, len(columns) + 1):
            ws.cell(row=total_row, column=column).fill = TOTAL_FILL
            ws.cell(row=total_row, column=column).border = Border(top=Side(style='double', color=BRAND))
    else:
        for column in range(1, len(columns) + 1):
            ws.cell(row=1, column=column).fill = HEADER_FILL
            ws.cell(row=1, column=column).font = HEADER_FONT
        _put(ws, 2, 1, 'No records in this period.').font = Font(italic=True, color=MUTED)
    for column, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(column)].width = min(max(width, 10), 48)
    ws.freeze_panes = 'A2'
    _print_setup(ws, report, title_rows='1:1')


def _print_setup(ws, report, title_rows=None):
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    if title_rows:
        ws.print_title_rows = title_rows
    ws.oddHeader.center.text = f'SMARTPOULTRY · {report.get_report_type_display()} · &A'
    ws.oddFooter.left.text = f'{report.start_date} to {report.end_date}'
    ws.oddFooter.right.text = 'Page &P of &N'


def build_report_workbook(report):
    records = report_records(report)
    wb = Workbook()
    wb.properties.title = report.title
    wb.properties.creator = 'SMARTPOULTRY'
    _summary_sheet(wb, report, records)

    _data_sheet(wb, report, 'Revenue', [
        ('Date', 'date'), ('Branch', 'text'), ('Type', 'text'), ('Flock', 'text'), ('Quantity', 'qty'), ('Unit', 'text'),
        ('Price Per Unit', 'rate'), ('Total Amount', 'money'), ('Egg Size', 'text'), ('Buyer Name', 'text'),
        ('Buyer Contact', 'text'), ('Buyer Address', 'text'), ('Order Number', 'text'), ('Transaction Number', 'text'), ('Notes', 'text'),
    ], [(r.date, r.branch.name if r.branch else '', r.get_revenue_type_display(), r.flock.flock_id if r.flock else '',
         r.quantity, r.unit, r.price_per_unit, r.total_amount, r.production.get_egg_size_display() if r.production_id else '',
         r.buyer_name, r.buyer_contact, r.buyer_address, r.order_number, r.transaction_number, r.notes)
        for r in records['revenue']], '2E7D32')

    _data_sheet(wb, report, 'Expenses', [
        ('Date', 'date'), ('Branch', 'text'), ('Type', 'text'), ('Description', 'text'), ('Category', 'text'),
        ('Amount', 'money'), ('Returned Quantity', 'qty'), ('Return Unit', 'text'), ('Returned Item', 'text'), ('Notes', 'text'),
    ], [(e.date, e.branch.name if e.branch else '', e.get_expense_type_display(), e.description, e.category, e.amount,
         e.return_quantity, e.return_unit, e.return_item_name, e.notes) for e in records['expenses']], 'C62828')

    _data_sheet(wb, report, 'Production', [
        ('Date', 'date'), ('Branch', 'text'), ('Product Type', 'text'), ('Flock', 'text'), ('Quantity', 'qty'),
        ('Unit', 'text'), ('Egg Size', 'text'), ('Notes', 'text'),
    ], [(p.date, p.branch.name if p.branch else '', p.get_product_type_display(), p.flock.flock_id, p.quantity, p.unit,
         p.get_egg_size_display(), p.notes) for p in records['production']], 'F9A825')

    _data_sheet(wb, report, 'Mortality', [
        ('Date', 'date'), ('Branch', 'text'), ('Flock', 'text'), ('Quantity', 'count'), ('Reason', 'text'),
        ('Description', 'text'), ('Notes', 'text'),
    ], [(m.date, m.branch.name if m.branch else '', m.flock.flock_id, m.quantity, m.get_reason_display(), m.description, m.notes)
        for m in records['mortality']], '6D4C41')

    _data_sheet(wb, report, 'Flocks', [
        ('Branch', 'text'), ('Flock ID', 'text'), ('Breed', 'text'), ('Quantity', 'count'), ('Status', 'text'),
        ('Date Added', 'date'), ('Expected Production Date', 'date'), ('Notes', 'text'),
    ], [(f.branch.name if f.branch else '', f.flock_id, f.get_breed_display(), f.quantity, f.get_status_display(),
         f.date_added, f.expected_production_date, f.notes) for f in records['flocks']], '1565C0')

    _data_sheet(wb, report, 'Inventory', [
        ('Type', 'text'), ('Name', 'text'), ('Quantity', 'qty'), ('Unit', 'text'), ('Cost Per Unit', 'rate'),
        ('Total Value', 'money'), ('Date Added', 'date'), ('Package Size', 'qty'), ('Content Unit', 'text'),
        ('Total Content', 'qty'), ('Notes', 'text'),
    ], [(i.get_item_type_display(), i.name, i.quantity, i.unit, i.cost_per_unit, i.total_value, i.date_added,
         i.package_size, i.content_unit, i.total_content, i.notes) for i in records['inventory']], '6A1B9A')

    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()
