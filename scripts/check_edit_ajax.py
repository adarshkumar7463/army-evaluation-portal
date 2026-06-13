import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'army_portal.settings')
import django
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
from departments.models import Agniveer
User = get_user_model()
client = Client()
agn = Agniveer.objects.first()
if not agn:
    print('No agniveer found')
    sys.exit(1)
# create or get registration user
username = 'reg_tester'
user, created = User.objects.get_or_create(username=username, defaults={'email': f'{username}@example.com', 'role': User.ROLE_REGISTRATION})
user.set_password('password')
user.role = User.ROLE_REGISTRATION
user.save()
logged = client.login(username=username, password='password')
print('login:', logged)
resp = client.get(f'/departments/registration/{agn.pk}/edit-ajax/')
print('status:', resp.status_code)
try:
    print('json keys:', list(resp.json().keys()))
except Exception as e:
    print('not json:', e)
