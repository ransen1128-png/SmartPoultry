"""Describe existing predictions without retraining or reopening model selection."""
import csv
import json
from pathlib import Path
import numpy as np
from evaluate_existing_age_model import metrics

ROOT=Path(__file__).resolve().parents[1]
run=Path(json.loads((ROOT/'reports/latest_age_finetuning.json').read_text())['run'])
with (run/'predictions.csv').open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
out=ROOT/'reports/age_evaluation_review';out.mkdir(exist_ok=True)
report={'status':'diagnostic_only','seed':2026,'new_training_performed':False,
    'independent_chicken_evaluation':False,
    'limitation':'Known source families only. Prior original-model corpus exposure and unresolved bird identities prevent unseen-chicken accuracy claims.',
    'partitions':{}}
for split in ('validation','test'):
    selected=[r for r in rows if r['split']==split]
    models={}
    for model in ('original','candidate'):
        values=[{**r,'prediction_months':float(r[model+'_prediction'])} for r in selected]
        families=sorted({r['source_family'] for r in values})
        family_errors={family:[abs(r['prediction_months']-float(r['age_months'])) for r in values if r['source_family']==family] for family in families}
        rng=np.random.default_rng(2026)
        draws=[np.mean([e for family in rng.choice(families,len(families),replace=True) for e in family_errors[family]]) for _ in range(2000)]
        models[model]={'metrics':metrics(values),'source_families':len(families),
            'descriptive_cluster_bootstrap_mae_interval_95':np.quantile(draws,[.025,.975]).tolist(),
            'per_age':{str(age):metrics([r for r in values if float(r['age_months'])==age]) for age in range(1,25)},
            'age_groups':{label:metrics([r for r in values if low<=float(r['age_months'])<=high]) for label,low,high in [('1-6',1,6),('7-12',7,12),('13-18',13,18),('19-24',19,24)]},
            'largest_errors':sorted(values,key=lambda r:abs(r['prediction_months']-float(r['age_months'])),reverse=True)[:5]}
        matrix=np.zeros((24,24),dtype=int)
        for row in values: matrix[int(float(row['age_months']))-1,int(np.clip(round(row['prediction_months']),1,24))-1]+=1
        with (out/f'{split}_{model}_confusion.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.writer(f);writer.writerow(['actual_age/predicted_age',*range(1,25)])
            for age,line in enumerate(matrix,1):writer.writerow([age,*line.tolist()])
    report['partitions'][split]=models
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'status':report['status'],'output':str(out),'test_photographs':len([r for r in rows if r['split']=='test'])}))
