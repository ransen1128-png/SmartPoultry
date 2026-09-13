import os
import sys
sys.path.insert(0, os.path.join(os.getcwd(), 'smartpoultry'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
import django
django.setup()
import core.urls as urls
print('urls file:', urls.__file__)
print('ROOT_URLCONF:', 'core.urls')
print('urlpatterns length:', len(urls.urlpatterns))
print('has farm_branches:', any(getattr(p, 'name', None) == 'farm_branches' for p in urls.urlpatterns))
print('named patterns:', [getattr(p, 'name', None) for p in urls.urlpatterns if getattr(p, 'name', None) is not None])
print('pattern reprs:')
for p in urls.urlpatterns:
    print(type(p), getattr(p, 'name', None), repr(p))
from django.urls import reverse
try:
    print('reverse farm_branches:', reverse('farm_branches'))
except Exception as e:
    print('reverse farm_branches error:', e)
from django.template import loader
base = loader.get_template('base.html')
print('template type:', type(base))
if hasattr(base, 'template') and hasattr(base.template, 'source'):
    source = base.template.source
    print('base.html source contains farm_branches:', "{% url 'farm_branches' %}" in source)
    for i, line in enumerate(source.splitlines(), 1):
        if 'farm_branches' in line or '/farm/branches/' in line:
            print(i, line)
else:
    print('could not inspect template source')
