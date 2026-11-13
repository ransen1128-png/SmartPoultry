"""Read-only legacy-sales review. No financial records are changed."""
import os
import sys
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'smartpoultry'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings')
import django
django.setup()
from revenue.models import Revenue
from revenue.reconciliation import review_sale
from django.db import connection

rows=[{'owner_id':sale.user_id,**review_sale(sale)} for sale in Revenue.objects.filter(production__isnull=True)]
out=ROOT/'.postgres-migration/legacy-stock-review.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({'database_backend':connection.vendor,'mutations':0,'pending_sales':rows},indent=2),encoding='utf-8')
print(json.dumps({'unlinked_sales':len(rows),'with_compatible_batch':sum(bool(r['candidates']) for r in rows),
                  'confirmed_or_changed':0,'review_report':str(out)}))
