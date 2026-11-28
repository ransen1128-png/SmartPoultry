"""Deterministic branch-specific Random Forest with chronological validation.
Only recorded, completed months become training labels. Missing months are not
invented as zero and the current partial month is never a completed-month label.
"""
from functools import lru_cache
import math
import hashlib,json
from datetime import date

MIN_MONTHS=4
MIN_VALIDATION_MONTHS = 3
MAX_VALIDATION_MONTHS = 6
SEED=2026


def features(history,target):
    recent=[value for _,value in history[-3:]]
    last_date,last_value=history[-1]
    gap=(target.year-last_date.year)*12+target.month-last_date.month
    return [last_value,sum(recent)/len(recent),math.sin(2*math.pi*target.month/12),math.cos(2*math.pi*target.month/12),gap]


@lru_cache(maxsize=128)
def fitted_forecast(scope,observations,targets):
    # scope isolates account/branch/target caches; it is not a model feature.
    history=[(date.fromisoformat(month),float(value)) for month,value in observations]
    report={'method':None,'status':'insufficient_history','observed_months':len(history),
        'minimum_months':MIN_MONTHS,'forecasts':[None]*len(targets),'validation_mae':None,
        'baseline_mae':None,'held_out_months':0,'training_samples':0,'seed':SEED}
    report['data_sha256']=hashlib.sha256(json.dumps(observations).encode()).hexdigest()
    if len(history)<MIN_MONTHS:return report
    from sklearn.ensemble import RandomForestRegressor
    from sklearn import __version__
    def model():return RandomForestRegressor(n_estimators=80,max_depth=4,min_samples_leaf=1,random_state=SEED,n_jobs=1)
    x=[features(history[:index],history[index][0]) for index in range(1,len(history))]
    y=[value for _,value in history[1:]]
    # Each validation prediction uses only records before its target month.
    validation_indices = range(max(MIN_MONTHS - 2, len(y) - MAX_VALIDATION_MONTHS), len(y))
    forest_errors = []
    baseline_errors = []
    for index in validation_indices:
        validation = model().fit(x[:index], y[:index])
        prediction = max(0.0, float(validation.predict([x[index]])[0]))
        forest_errors.append(abs(prediction - y[index]))
        baseline_errors.append(abs(history[index][1] - y[index]))
    held_out_months = len(forest_errors)
    forest_mae = sum(forest_errors) / held_out_months
    baseline_mae = sum(baseline_errors) / held_out_months
    use_forest = forest_mae < baseline_mae
    if use_forest:
        forest = model().fit(x, y)
        working = list(history)
        predictions = []
        for target in targets:
            month = date.fromisoformat(target)
            value = max(0.0, float(forest.predict([features(working, month)])[0]))
            predictions.append(round(value, 2))
            working.append((month, value))
    else:
        predictions = [round(history[-1][1], 2)] * len(targets)
    report.update(status='trained', method='Random Forest' if use_forest else 'Previous-value baseline',
        provisional=held_out_months < MIN_VALIDATION_MONTHS,
        forecasts=predictions,validation_mae=round(forest_mae,2),
        baseline_mae=round(baseline_mae,2),held_out_months=held_out_months,training_samples=len(y),
        validation_month=history[-1][0].isoformat(),validation_training_ends=history[-2][0].isoformat(),
        feature_names=['previous recorded value','recent average','month sine','month cosine','months since previous observation'],
        sklearn_version=__version__)
    return report


def random_forest_forecast(scope,monthly_values,current_month,future_months):
    history=tuple((month.isoformat(),float(value)) for month,value in sorted(monthly_values.items()) if month<current_month)
    return fitted_forecast(scope,history,tuple(month.isoformat() for month in future_months))
