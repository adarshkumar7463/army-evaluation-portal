import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'army_portal.settings')
import django
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from departments.models import Agniveer
User = get_user_model()
client = Client()
agn = Agniveer.objects.first()
if not agn:
    print('No agniveer found')
    sys.exit(1)
username = 'reg_tester2'
user, created = User.objects.get_or_create(username=username, defaults={'email': f'{username}@example.com'})
user.set_password('password')
# ensure registration role
try:
    user.role = User.ROLE_REGISTRATION
except Exception:
    # fallback if role field differs
    pass
user.save()
logged = client.login(username=username, password='password')
print('login:', logged)
from datetime import date
post_data = {
    'agniveer_no': agn.agniveer_no or 'TEST123',
    'name': agn.name or 'Test Name',
    'father_name': agn.father_name or 'Father',
    'dor': (agn.dor.isoformat() if agn.dor else date.today().isoformat()),
    'status': agn.status or 'active'
}
img = SimpleUploadedFile('photo.jpg', b'fakeimagebytes', content_type='image/jpeg')
resp = client.post(f'/departments/registration/{agn.pk}/edit-ajax/', data=post_data, files={'photo': img})
print('status', resp.status_code)
try:
    print('json:', resp.json())
except Exception as e:
    print('response content:', resp.content[:200], 'error:', e)
