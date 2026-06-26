import os
import sys
import django

# Add current directory to path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'army_portal.settings')
django.setup()

from django.contrib.auth import get_user_model
from chatbot.services import get_sandboxed_db, interpret_query_direct

User = get_user_model()
# Let's find a user who has access, e.g. a commander or superuser
cmd_user = User.objects.filter(role='commander').first()
if not cmd_user:
    cmd_user = User.objects.create_user(username='temp_cmd', password='pwd', role='commander')

mem_conn = get_sandboxed_db(cmd_user)

# 1. First query: top ranker in bpet
res1 = interpret_query_direct("top ranker in bpet", mem_conn, user=cmd_user)
print("Query 1 result:")
print(f"Success: {res1.get('success')}")
print(f"Intent: {res1.get('intent')}")
print(f"Filters: {res1.get('filters')}")
print(f"Answer: {res1.get('answer')}")

# 2. Second query: top ranker in CMK
last_intent = res1.get('intent')
last_filters = res1.get('filters')
res2 = interpret_query_direct("top ranker in CMK", mem_conn, last_intent=last_intent, last_filters=last_filters, user=cmd_user)
print("\nQuery 2 result:")
print(f"Success: {res2.get('success')}")
print(f"Intent: {res2.get('intent')}")
print(f"Filters: {res2.get('filters')}")
print(f"Answer: {res2.get('answer')}")

# 3. Third query: overall top ranker in CMK
res3 = interpret_query_direct("overall top ranker in CMK", mem_conn, last_intent=last_intent, last_filters=last_filters, user=cmd_user)
print("\nQuery 3 result:")
print(f"Success: {res3.get('success')}")
print(f"Intent: {res3.get('intent')}")
print(f"Filters: {res3.get('filters')}")
print(f"Answer: {res3.get('answer')}")

mem_conn.close()
