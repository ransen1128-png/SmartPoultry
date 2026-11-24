"""Measure SmartPoultry's forecast accuracy on a farm's real monthly records.

Input CSV columns: month (YYYY-MM), revenue, expenses, eggs. Leave a cell blank when
the farm has no record for that month. Past paper or notebook records can be used.

Each month after the fourth is forecast using only the earlier months, by the same
code the website uses, and is compared with what really happened. The baseline is
"use the latest recorded month". Do not use invented or sample data for the manuscript.

Run:  .venv\\Scripts\\python.exe tools\\forecast_backtest.py farm1.csv [farm2.csv ...]
"""
import csv
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'smartpoultry'))
SERIES = ('revenue', 'expenses', 'eggs')
SMALL_SAMPLE = 12


def read_farm(path):
    data = {name: {} for name in SERIES}
    with open(path, newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        missing = {'month', *SERIES} - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f'{path}: missing column(s) {", ".join(sorted(missing))}')
        for line, row in enumerate(reader, 2):
            try:
                month = date.fromisoformat(row['month'].strip() + '-01')
                for name in SERIES:
                    text = (row[name] or '').strip().replace(',', '')
                    if text:
                        value = float(text)
                        if value < 0 or value != value:
                            raise ValueError('values cannot be negative')
                        if month in data[name]:
                            raise ValueError(f'month {row["month"]} appears twice')
                        data[name][month] = value
            except ValueError as error:
                raise SystemExit(f'{path} line {line}: {error}')
    return data


def backtest(values, scope):
    """Return (actual, forecast, baseline) for every month that has four earlier months."""
    from core.random_forest_forecast import MIN_MONTHS, random_forest_forecast
    months = sorted(values)
    results = []
    for index in range(MIN_MONTHS, len(months)):
        target = months[index]
        history = {month: values[month] for month in months[:index]}
        forecast = random_forest_forecast(scope, history, target, [target])['forecasts'][0]
        results.append((values[target], forecast, values[months[index - 1]]))
    return results


def summarize(results):
    actual = sum(a for a, _, _ in results)
    model = sum(abs(a - f) for a, f, _ in results)
    base = sum(abs(a - b) for a, _, b in results)
    count = len(results)
    return {'tests': count, 'mae': model / count, 'baseline_mae': base / count,
            'error_pct': 100 * model / actual if actual else None, 'baseline_pct': 100 * base / actual if actual else None}


def main(paths):
    if not paths:
        raise SystemExit(__doc__)
    pooled = {name: [] for name in SERIES}
    for path in paths:
        for name, values in read_farm(path).items():
            pooled[name] += backtest(values, f'backtest:{path}:{name}')
    pct = lambda value: 'n/a' if value is None else f'{value:.1f}%'
    print(f'Farms: {len(paths)}')
    print(f'{"Series":10} {"Months tested":>13} {"Model MAE":>12} {"Baseline MAE":>13} {"Model error":>12} {"Baseline error":>15}  Better')
    for name in SERIES:
        if not pooled[name]:
            print(f'{name:10} {0:>13}  not enough history: five or more recorded months are needed')
            continue
        s = summarize(pooled[name])
        better = 'tie' if abs(s['mae'] - s['baseline_mae']) < 1e-9 else 'model' if s['mae'] < s['baseline_mae'] else 'baseline'
        print(f'{name:10} {s["tests"]:>13} {s["mae"]:>12.2f} {s["baseline_mae"]:>13.2f} {pct(s["error_pct"]):>12} {pct(s["baseline_pct"]):>15}  {better}')
        if s['tests'] < SMALL_SAMPLE:
            print(f'{"":10} Only {s["tests"]} tested month(s): describe this as limited evidence.')


if __name__ == '__main__':
    main(sys.argv[1:])
