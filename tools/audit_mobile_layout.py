"""Measure page overflow in real Chrome with an isolated owner session."""
import os,sys,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'smartpoultry'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser()
parser.add_argument('--width',type=int,default=390)
width_limit=parser.parse_args().width
user=get_user_model().objects.get(pk=3)
session=SessionStore();session['_auth_user_id']=str(user.pk);session['_auth_user_backend']='django.contrib.auth.backends.ModelBackend';session['_auth_user_hash']=user.get_session_auth_hash();session.save()
out=ROOT/f'.postgres-migration/mobile-audit-{width_limit}';out.mkdir(exist_ok=True)
results=[]
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='chrome',headless=True)
  context=browser.new_context(viewport={'width':width_limit,'height':844},is_mobile=True,has_touch=True)
  context.add_cookies([{'name':'sessionid','value':session.session_key,'url':'http://127.0.0.1:8000'}])
  page=context.new_page()
  for path in ['dashboard/','farm/branches/','flocks/','production-records/','production-records/add/','mortality-records/','mortality-records/add/','inventory/','revenue/','expenses/','settings/','reports/','rooster-age-estimator/']:
   response=page.goto('http://127.0.0.1:8000/'+path,wait_until='networkidle')
   item={'path':path,'http':response.status,'requested_width':width_limit}
   item.update(page.evaluate('''limit => ({viewport:innerWidth, width:document.documentElement.scrollWidth, overflow:[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>limit+2 && !e.closest('.table-responsive') && getComputedStyle(e).position!=='absolute').slice(0,12).map(e=>({tag:e.tagName,cls:e.className}))})''',width_limit))
   item['fits_screen']=item['width']<=width_limit+2
   results.append(item)
   if response.status==200:page.screenshot(path=str(out/(path.replace('/','_')+'.png')),full_page=True)
   target={'inventory/':'#addInventoryModal','revenue/':'#addRevenueModal','expenses/':'#addExpenseModal'}.get(path)
   if target:
    page.locator('[data-bs-target="'+target+'"]').click()
    page.locator(target).wait_for(state='visible')
    width=page.evaluate('document.documentElement.scrollWidth')
    results.append({'path':path+' add dialog','requested_width':width_limit,'width':width,'fits_screen':width<=width_limit+2})
   if path=='settings/':
    page.locator('#security-tab').click()
    page.locator('#security-panel').wait_for(state='visible')
    width=page.evaluate('document.documentElement.scrollWidth')
    results.append({'path':path+' security','requested_width':width_limit,'width':width,'fits_screen':width<=width_limit+2})
  browser.close()
 print(json.dumps(results,indent=2));(out/'report.json').write_text(json.dumps(results,indent=2))
finally:session.delete()
