"""Deterministic branch-specific Random Forest with chronological validation.
Only recorded, completed months become training labels. Missing months are not
invented as zero and the current partial month is never a completed-month label.
"""
from functools import lru_cache
import math
import hashlib,json
from datetime import date

MIN_MONTHS=4
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
    report={'method':'Random Forest','status':'insufficient_history','observed_months':len(history),
        'minimum_months':MIN_MONTHS,'forecasts':[None]*len(targets),'validation_mae':None,
        'baseline_mae':None,'held_out_months':0,'training_samples':0,'seed':SEED}
    report['data_sha256']=hashlib.sha256(json.dumps(observations).encode()).hexdigest()
    if len(history)<MIN_MONTHS:return report
    from sklearn.ensemble import RandomForestRegressor
    from sklearn import __version__
    def model():return RandomForestRegressor(n_estimators=80,max_depth=4,min_samples_leaf=1,random_state=SEED,n_jobs=1)
    x=[features(history[:index],history[index][0]) for index in range(1,len(history))]
    y=[value for _,value in history[1:]]
    validation=model().fit(x[:-1],y[:-1])
    held_out=max(0,float(validation.predict([x[-1]])[0]))
    forest=model().fit(x,y)
    working=list(history);predictions=[]
    for target in targets:
        month=date.fromisoformat(target)
        value=max(0,float(forest.predict([features(working,month)])[0]))
        predictions.append(round(value,2));working.append((month,value))
    report.update(status='trained',forecasts=predictions,validation_mae=round(abs(held_out-y[-1]),2),
        baseline_mae=round(abs(history[-2][1]-y[-1]),2),held_out_months=1,training_samples=len(y),
        validation_month=history[-1][0].isoformat(),validation_training_ends=history[-2][0].isoformat(),
        feature_names=['previous recorded value','recent average','month sine','month cosine','months since previous observation'],
        sklearn_version=__version__,limitation='One held-out month is a limited validation, not established forecast accuracy.')
    return report


def random_forest_forecast(scope,monthly_values,current_month,future_months):
    history=tuple((month.isoformat(),float(value)) for month,value in sorted(monthly_values.items()) if month<current_month)
    return fitted_forecast(scope,history,tuple(month.isoformat() for month in future_months))
