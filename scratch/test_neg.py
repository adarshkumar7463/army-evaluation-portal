import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'army_portal.settings')
django.setup()

from django.contrib.auth import get_user_model
from departments.models import Agniveer
from chatbot.services import get_sandboxed_db, interpret_query_direct

User = get_user_model()
cmd = User.objects.filter(role='commander').first()
if not cmd:
    cmd = User.objects.create_user(username='test_cmd_1', password='pwd', role='commander')

# Clean existing to ensure predictable test environment
Agniveer.objects.all().delete()
ag1 = Agniveer.objects.create(name="Agniveer One", agniveer_no="AGN/1001", trade="CLK", bn_desp="1TB", status="active")
ag2 = Agniveer.objects.create(name="Agniveer Two", agniveer_no="AGN/1002", trade="DMV", bn_desp="2TB", status="fail")

mem_conn = get_sandboxed_db(cmd)
res = interpret_query_direct("list trainees but not DMV trade", mem_conn, user=cmd)
print("Success:", res.get('success'))
print("SQL:", res.get('sql'))
print("Rows:", res.get('rows'))
print("Answer:", res.get('answer'))
print("Filters:", res.get('filters'))

mem_conn.close()
