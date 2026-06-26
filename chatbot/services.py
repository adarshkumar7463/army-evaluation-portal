import re
import json
import sqlite3
import urllib.request
import sqlparse
from django.conf import settings
from departments.models import Agniveer
from evaluation.models import EvaluationSheet, Marks
from evaluation.result_helpers import get_bn_desp_q


def get_filtered_querysets(user):
    """
    Get the filtered querysets for Agniveer, EvaluationSheet, and Marks
    based on the user's role and subdepartment restrictions.
    """
    agniveers = Agniveer.objects.all()
    dept = user.get_department_code()

    # Commander, G-Head, and Superuser can see everything
    if user.can_view_all or user.is_superuser:
        pass
    else:
        # TTS (Dept B) Filters
        if dept == 'B' and hasattr(user, 'tts_trade') and user.tts_trade:
            if user.tts_trade == 'DMV':
                agniveers = agniveers.filter(trade='DMV')
            elif user.tts_trade == 'OPEM':
                agniveers = agniveers.filter(trade='OPEM')
            elif user.tts_trade == 'OTHER':
                agniveers = agniveers.exclude(trade__in=['DMV', 'OPEM'])
        # Clerk (Dept D) Filters
        elif dept == 'D':
            agniveers = agniveers.filter(trade__in=['CLK', 'CLERK', 'Clerk', 'CLK_SD', 'CLK_IM'])
        # Battalion (Dept A) Filters
        elif user.is_battalion and getattr(user, 'battalion_unit', None):
            agniveers = agniveers.filter(get_bn_desp_q('bn_desp', user.battalion_unit))

        # Platoon / Company level constraints
        if hasattr(user, 'company') and user.company:
            agniveers = agniveers.filter(company=user.company)
        if hasattr(user, 'platoon') and user.platoon:
            agniveers = agniveers.filter(platoon=user.platoon)

    # Filter evaluation sheets
    sheets = EvaluationSheet.objects.filter(agniveer__in=agniveers)
    if not (user.can_view_all or user.is_superuser):
        if dept:
            sheets = sheets.filter(department=dept)
            if dept == 'B' and hasattr(user, 'tts_trade') and user.tts_trade:
                trade = user.tts_trade
                if trade == 'DMV':
                    sheets = sheets.filter(test_type__startswith='DMV_')
                elif trade == 'OPEM':
                    sheets = sheets.filter(test_type__startswith='OPEM_')
                else:
                    sheets = sheets.exclude(test_type__startswith='DMV_').exclude(test_type__startswith='OPEM_')

    # Filter marks
    marks = Marks.objects.filter(evaluation_sheet__in=sheets)

    return agniveers, sheets, marks


def populate_sandbox_db(mem_conn, main_conn, agniveers, sheets, marks, users, logs, can_view_all=False):
    """
    Populates an in-memory SQLite database connection with data from the authorized querysets.
    """
    # 1. Recreate schemas in memory
    tables = [
        'departments_agniveer',
        'evaluation_evaluationsheet',
        'evaluation_marks',
        'accounts_customuser',
        'logs_activitylog'
    ]
    for table in tables:
        cursor = main_conn.cursor()
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}';")
        row = cursor.fetchone()
        if row:
            mem_conn.execute(row[0])

    # Helper function to copy table data
    def copy_table_data(table_name, queryset):
        cursor = main_conn.cursor()
        if can_view_all:
            cursor.execute(f"SELECT * FROM {table_name};")
        else:
            ids = list(queryset.values_list('id', flat=True))
            if not ids:
                return
            cursor.execute(f"SELECT * FROM {table_name} WHERE id IN ({','.join(map(str, ids))});")
            
        rows = cursor.fetchall()
        if rows:
            col_names = [d[0] for d in cursor.description]
            placeholders = ','.join(['?'] * len(col_names))
            mem_conn.executemany(f"INSERT INTO {table_name} ({','.join(col_names)}) VALUES ({placeholders})", rows)

    copy_table_data('departments_agniveer', agniveers)
    copy_table_data('evaluation_evaluationsheet', sheets)
    copy_table_data('evaluation_marks', marks)
    copy_table_data('accounts_customuser', users)
    copy_table_data('logs_activitylog', logs)

    # Redact passwords for security before committing sandbox
    mem_conn.execute("UPDATE accounts_customuser SET password = 'REDACTED';")
    mem_conn.commit()


def get_sandboxed_db(user):
    """
    Creates and returns an in-memory SQLite connection loaded with authorized records only.
    """
    from accounts.models import CustomUser
    from logs.models import ActivityLog

    from django.db import connection
    connection.ensure_connection()
    main_conn = connection.connection
    mem_conn = sqlite3.connect(':memory:')

    try:
        agniveers, sheets, marks = get_filtered_querysets(user)
        if user.can_view_all or user.is_superuser:
            users = CustomUser.objects.all()
            logs = ActivityLog.objects.all()
        else:
            users = CustomUser.objects.filter(id=user.id)
            logs = ActivityLog.objects.filter(user=user)

        populate_sandbox_db(
            mem_conn, main_conn, agniveers, sheets, marks, users, logs,
            can_view_all=(user.can_view_all or user.is_superuser)
        )
    finally:
        pass

    return mem_conn


def query_ollama(model, prompt, temperature=0.1, max_tokens=150):
    """
    Queries the local Ollama instance with a given model and prompt.
    """
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens
        }
    }
    headers = {'Content-Type': 'application/json'}
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            res = json.loads(response.read().decode('utf-8'))
            return res.get('response', '').strip()
    except Exception as e:
        raise ConnectionError(f"Local AI model server (Ollama) is offline or unreachable: {str(e)}")


def validate_sql_query(sql):
    """
    Verifies that the generated SQL query is a single, safe, read-only SELECT statement.
    """
    parsed = sqlparse.parse(sql)
    if not parsed:
        raise ValueError("Invalid SQL syntax or empty query.")

    if len(parsed) > 1:
        raise ValueError("Only a single SQL statement is allowed.")

    stmt = parsed[0]
    if stmt.get_type() != 'SELECT':
        raise ValueError("Only SELECT queries are allowed for security.")

    dangerous_keywords = [
        'insert', 'update', 'delete', 'drop', 'alter', 'create', 'replace',
        'truncate', 'grant', 'revoke', 'vacuum', 'pragma', 'execute', 'exec',
        'union'
    ]
    sql_lower = sql.lower()
    for keyword in dangerous_keywords:
        if f" {keyword} " in f" {sql_lower} " or sql_lower.startswith(f"{keyword} ") or sql_lower.endswith(f" {keyword}"):
            raise ValueError(f"Unauthorized database keyword '{keyword}' detected.")


def generate_sql_from_question(model, question, user):
    """
    Translates user's question into a SQLite SELECT query using the local LLM.
    """
    dept_code = user.get_department_code()
    role_display = user.get_role_display()
    
    user_context = f"Role: {role_display}"
    if dept_code:
        user_context += f", Department: {dept_code}"
    if getattr(user, 'battalion_unit', None):
        user_context += f", Unit: {user.battalion_unit}"
    if getattr(user, 'tts_trade', None):
        user_context += f", Trade: {user.tts_trade}"
    if getattr(user, 'company', None):
        user_context += f", Company: {user.company}"
    if getattr(user, 'platoon', None):
        user_context += f", Platoon: {user.platoon}"

    schema_desc = """
Table: departments_agniveer
Columns:
  id (INTEGER) PRIMARY KEY
  enrollment_number (varchar(30)) -- unique identifier, format: AGN-YYYYMMDD-XXXX
  agniveer_no (varchar(30)) -- official number
  name (varchar(100)) -- trainee name
  father_name (varchar(100)) -- trainee's father name
  trade (varchar(20)) -- trainee trade: 'CLK' (Clerk), 'DMV' (Driver), 'OPEM', 'Other'
  bn_desp (varchar(10)) -- battalion unit designation: '1TB', '2TB', 'STB'
  company (varchar(20)) -- e.g. Tirah Company, Megiddo Company, Ghuznee Company, Maktila Company, Cassino Company, Pigris Company, Company A, Company B, Company C
  platoon (varchar(10)) -- e.g. P1, P2, P3...
  status (varchar(20)) -- 'active', 'completed', 'dropped', 'pass', 'fail'
  dor (date) -- date of reporting
  joining_date (date)

Table: evaluation_evaluationsheet
Columns:
  id (INTEGER) PRIMARY KEY
  category (varchar(20)) -- category of test: 'physical', 'weapon', 'field', 'assessment', 'result'
  test_type (varchar(20)) -- specific test type: 'PPT', 'BPET', 'Firing', 'DST', 'MR_III', 'BFC', 'PDP', 'CMK_SHEET', 'WPN_HANDLING', 'FINAL_RESULT'
  department (varchar(1)) -- 'A' (Battalion), 'B' (TTS), 'C' (CS), 'D' (Clerk)
  evaluation_date (date)
  is_locked (bool)
  agniveer_id (bigint) -- FK to departments_agniveer.id
  sub_event_results (TEXT) -- JSON field: e.g. {"Marks": {"Online Test (100)": 85, "Practical Test (50)": 40}} or {"100M Sprint": "14 Sec", "2.4 KM Run": "10:15"}

Table: evaluation_marks
Columns:
  id (INTEGER) PRIMARY KEY
  evaluation_sheet_id (bigint) -- FK to evaluation_evaluationsheet.id
  evaluator_type (varchar(10)) -- 'admin'
  marks (smallint unsigned) -- numeric score for this sheet

Table: accounts_customuser
Columns:
  id (INTEGER) PRIMARY KEY
  username (varchar(150))
  first_name (varchar(150))
  last_name (varchar(150))
  email (varchar(254))
  role (varchar(20)) -- e.g. 'commander', 'g_head', 'dept_a', 'dept_b', 'dept_c', 'dept_d', 'registration'
  department (varchar(1)) -- 'A', 'B', 'C', 'D'
  battalion_unit (varchar(10)) -- '1TB', '2TB', 'STB'
  tts_trade (varchar(10)) -- 'DMV', 'OPEM', 'OTHER'
  company (varchar(20))
  platoon (varchar(10))
  rank (varchar(50))
  service_number (varchar(30))
  is_active (bool)

Table: logs_activitylog
Columns:
  id (INTEGER) PRIMARY KEY
  user_id (bigint) -- FK to accounts_customuser.id
  role (varchar(20))
  action (varchar(20)) -- 'LOGIN', 'LOGOUT', 'CREATE', 'UPDATE', 'DELETE', 'VIEW', 'EXPORT', 'EVALUATE', 'LOCK'
  description (TEXT)
  ip_address (char(39))
  timestamp (datetime)
    """

    prompt = f"""You are a SQLite SQL Generator. Given the database schema below, write a single SQL query that answers the user's question.
Do not write any explanation. Do not write anything other than the SQL query inside a ```sql ... ``` code block.

Schema:
{schema_desc}

User role & context: {user_context}

RULES FOR SQL GENERATION:
1. Status mappings:
   - "passed" / "passed agniveer" -> status = 'pass'
   - "failed" / "failed agniveer" -> status = 'fail'
   - "active" / "active agniveer" -> status = 'active'
   - "completed" -> status = 'completed'
   - "dropped" / "dropped out" -> status = 'dropped'

2. Department mappings:
   - "Battalion" or "Dept A" or "1TB" or "2TB" or "STB" -> department = 'A'
   - "TTS" or "Dept B" or "Technical Training" -> department = 'B'
   - "CS" or "CES" or "Communication System" or "Dept C" -> department = 'C'
   - "Clerk" or "Dept D" or "Clerical" -> department = 'D'

3. Mappings for Agniveers to Departments:
   - Trainees (departments_agniveer) do not have a department column. To query Agniveers in a specific department, JOIN departments_agniveer with evaluation_evaluationsheet:
     `SELECT a.* FROM departments_agniveer a JOIN evaluation_evaluationsheet s ON a.id = s.agniveer_id WHERE s.department = 'C'` (for CS/CES).
   - "Agniveers in CS/CES department" -> Join with evaluation_evaluationsheet where department = 'C'.
   - "Agniveers in Clerk department" -> Join with evaluation_evaluationsheet where department = 'D'.
   - "Agniveers in TTS department" -> Join with evaluation_evaluationsheet where department = 'B'.
   - "Agniveers in Battalion department" -> Join with evaluation_evaluationsheet where department = 'A'.

4. Trade code mappings (use EXACT UPPERCASE codes):
   - "OPEM" -> trade = 'OPEM'
   - "DMV" / "Driver" -> trade = 'DMV'
   - "Clerk" / "CLK" -> trade = 'CLK'
   - CS trades -> trade IN ('ELET', 'OPR_RADIO', 'RST')
   - TTS trades -> trade IN ('DMV', 'OPEM', 'A/CONSTR', 'AWW', 'P&D', 'FTR_MACH', 'WELDER', 'SVY_TOPO', 'DTMN_TECH', 'AFV')

5. Performance / ranking calculations:
   - "who is first in firing" -> JOIN marks, sheet, and agniveer, filter by test_type = 'Firing', ORDER BY marks DESC LIMIT 1.
   - "who is first in PPT" -> test_type = 'PPT', ORDER BY marks DESC LIMIT 1.
   - "who is first in DMV" -> test_type = 'DMV_RESULT' or trade = 'DMV', join marks and order by marks DESC LIMIT 1.
   - "who is first in CES/CS" -> Join agniveer, sheet, marks, filter by department = 'C', order by marks DESC LIMIT 1.

6. Logs and Users queries:
   - "list all users" or "users details" -> Query accounts_customuser table.
   - "activity logs" or "logs details" -> Query logs_activitylog table. Join with accounts_customuser if username is needed.

Examples:
User: How many Agniveers are there in 1TB battalion?
SQL:
```sql
SELECT COUNT(*) FROM departments_agniveer WHERE bn_desp = '1TB';
```

User: Find all Agniveers in CS/CES department.
SQL:
```sql
SELECT DISTINCT a.* FROM departments_agniveer a JOIN evaluation_evaluationsheet s ON a.id = s.agniveer_id WHERE s.department = 'C';
```

User: How many agniveers in tts opem department?
SQL:
```sql
SELECT COUNT(*) FROM departments_agniveer WHERE trade = 'OPEM';
```

User: How many agniveers are passed?
SQL:
```sql
SELECT COUNT(*) FROM departments_agniveer WHERE status = 'pass';
```

User: Who is first in firing test in battalion?
SQL:
```sql
SELECT a.name, m.marks FROM evaluation_marks m 
JOIN evaluation_evaluationsheet s ON m.evaluation_sheet_id = s.id 
JOIN departments_agniveer a ON s.agniveer_id = a.id
WHERE s.test_type = 'Firing' AND s.department = 'A'
ORDER BY m.marks DESC LIMIT 1;
```

User: Show all activity logs for user admin.
SQL:
```sql
SELECT l.* FROM logs_activitylog l
JOIN accounts_customuser u ON l.user_id = u.id
WHERE u.username = 'admin';
```

Now write the SQL query for this question:
User: {question}
SQL:"""

    response = query_ollama(model, prompt, temperature=0.1, max_tokens=80)

    # Extract SQL block
    match = re.search(r'```sql\s*(.*?)\s*```', response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return response.strip()


def execute_sandboxed_query(mem_conn, sql, params=None):
    """
    Executes SQL on the sandboxed connection, returns column names and row results.
    """
    cursor = mem_conn.cursor()
    if params:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql)
    col_names = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    return col_names, rows


def generate_friendly_answer(model, question, sql, col_names, results):
    """
    Uses the local LLM to explain the SQL query results in a clear and professional manner.
    """
    # Prepare small result JSON for prompt context
    res_list = []
    for row in results[:50]:  # Limit size for prompt context
        res_list.append(dict(zip(col_names, row)))
    results_str = json.dumps(res_list, indent=2)

    prompt = f"""You are a helpful and professional database chatbot for the Army Evaluation Portal.
A user asked: "{question}"

We ran this SQL query to retrieve the answer:
{sql}

The query returned the following results:
{results_str}

Write a direct, clear, and professional response answering the user's question based on these results.
If there are no results, politely state that no matching records were found.
Keep the answer brief and to the point (maximum 1-3 sentences). Do NOT include any markdown tables or lists of records, as the user-facing table will be automatically rendered directly from the database output. Just provide a brief natural language summary introduction.

Answer:"""
    return query_ollama(model, prompt, temperature=0.3, max_tokens=200)


def interpolate_sql_for_display(sql, params):
    """
    Formats the SQL statement with parameter values for user-facing log display.
    """
    if not params:
        return sql
    parts = sql.split('?')
    interpolated = ""
    for i, part in enumerate(parts[:-1]):
        val = params[i]
        if isinstance(val, str):
            val_escaped = val.replace("'", "''")
            interpolated += f"{part}'{val_escaped}'"
        else:
            interpolated += f"{part}{val}"
    interpolated += parts[-1]
    return interpolated


def extract_lexicon(mem_conn):
    """
    Scans the SQLite sandboxed DB to extract unique entities.
    Because the sandbox is pre-filtered by the user's role constraints,
    this lexicon is inherently secure and scoped.
    """
    cursor = mem_conn.cursor()

    def get_column_values(table, column):
        try:
            cursor.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL AND {column} != '';")
            return [row[0] for row in cursor.fetchall()]
        except Exception:
            return []

    companies = get_column_values('departments_agniveer', 'company')
    platoons = get_column_values('departments_agniveer', 'platoon')
    trades = get_column_values('departments_agniveer', 'trade')
    battalions = get_column_values('departments_agniveer', 'bn_desp')
    names = get_column_values('departments_agniveer', 'name')
    agniveer_nos = get_column_values('departments_agniveer', 'agniveer_no')
    test_types = get_column_values('evaluation_evaluationsheet', 'test_type')
    categories = get_column_values('evaluation_evaluationsheet', 'category')
    usernames = get_column_values('accounts_customuser', 'username')
    actions = get_column_values('logs_activitylog', 'action')

    return {
        'companies': companies,
        'platoons': platoons,
        'trades': trades,
        'battalions': battalions,
        'names': names,
        'agniveer_nos': agniveer_nos,
        'test_types': test_types,
        'categories': categories,
        'usernames': usernames,
        'actions': actions
    }


def format_direct_response_nl(question, sql, col_names, rows, filters, intent, limit_num):
    """
    Generates a clear and structured natural language response for direct SQL results.
    """
    if not rows:
        return "No records were found matching your query."

    filter_descs = []
    if 'status' in filters:
        filter_descs.append(f"status: {filters['status']}")
    if 'company' in filters:
        filter_descs.append(f"company: {filters['company']}")
    if 'platoon' in filters:
        filter_descs.append(f"platoon: {filters['platoon']}")
    if 'trade' in filters:
        filter_descs.append(f"trade: {filters['trade']}")
    if 'bn_desp' in filters:
        filter_descs.append(f"unit: {filters['bn_desp']}")
    if 'name' in filters:
        filter_descs.append(f"name: {filters['name']}")
    if 'agniveer_no' in filters:
        filter_descs.append(f"agniveer number: {filters['agniveer_no']}")
    if 'test_type' in filters:
        filter_descs.append(f"test type: {filters['test_type']}")
    if 'category' in filters:
        filter_descs.append(f"category: {filters['category']}")
    if 'department' in filters:
        filter_descs.append(f"department: {filters['department']}")
    if 'username' in filters:
        filter_descs.append(f"user: {filters['username']}")
    if 'action' in filters:
        filter_descs.append(f"action: {filters['action']}")

    filter_str = ", ".join(filter_descs)
    if filter_str:
        filter_str = f" ({filter_str})"

    if intent == 'count':
        count_val = rows[0][0]
        if 'status' in filters and 'company' in filters:
            return f"There are **{count_val}** {filters['status']} Agniveers in {filters['company']}."
        elif 'status' in filters:
            return f"There are **{count_val}** {filters['status']} Agniveers found in the system."
        elif 'company' in filters:
            return f"The total number of registered Agniveers in {filters['company']} is **{count_val}**."
        else:
            return f"The total count of matching records is **{count_val}**{filter_str}."

    elif intent == 'groupby':
        grouped_col = col_names[0]
        friendly_col = grouped_col.replace("a.", "").replace("s.", "").replace("_", " ").title()
        if friendly_col == "Bn Desp":
            friendly_col = "Unit"
        return f"Here is the breakdown of records by **{friendly_col}**{filter_str}:"

    elif intent == 'average':
        avg_val = rows[0][0]
        if avg_val is None:
            return "No score records were found to calculate the average."
        avg_val = round(avg_val, 2)
        if 'test_type' in filters and 'company' in filters:
            return f"The average score in **{filters['test_type']}** for Agniveers in {filters['company']} is **{avg_val}**."
        elif 'test_type' in filters:
            return f"The average score for test **{filters['test_type']}** is **{avg_val}**."
        else:
            return f"The average score is **{avg_val}**{filter_str}."

    elif intent in ['max', 'min']:
        if len(rows) == 1:
            if len(rows[0]) >= 8:
                name = rows[0][0]
                trade = rows[0][3]
                company = rows[0][4]
                platoon = rows[0][5]
                test_type = rows[0][6]
                marks = rows[0][7]
            else:
                name, marks, test_type, trade, company, platoon = rows[0]
            term = "highest" if intent == 'max' else "lowest"
            return f"The trainee with the **{term}** score in {test_type} is **{name}** ({company}, {platoon}, {trade} trade) with **{marks}** marks."
        else:
            term = "Top" if intent == 'max' else "Bottom"
            test_desc = f" in {filters['test_type']}" if 'test_type' in filters else ""
            return f"Here are the **{term} {len(rows)}** performers{test_desc}{filter_str}:"

    elif intent == 'logs':
        return f"Here are the recent activity logs matching your query{filter_str}:"

    elif intent == 'users':
        return f"Here is the list of users found:"

    else:
        return f"Here are the matching database records{filter_str}:"


def get_edit_distance(s1, s2):
    """
    Computes the Levenshtein edit distance between two strings.
    """
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2+1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
        distances = distances_
    return distances[-1]


def fuzzy_match(word, choices, threshold=0.75, split_choices=False):
    """
    Fuzzy matches a word against a list of choices using edit distance similarity.
    Includes length difference pre-filtering for high performance.
    """
    best_match = None
    best_score = 0
    w_len = len(word)
    if w_len < 3:
        return None
    for choice in choices:
        c_clean = choice.lower().strip()
        
        if split_choices and " " in c_clean:
            sub_words = c_clean.split()
            for sub_w in sub_words:
                if len(sub_w) < 3:
                    continue
                if abs(w_len - len(sub_w)) > 2:
                    continue
                dist = get_edit_distance(word, sub_w)
                max_len = max(w_len, len(sub_w))
                if max_len == 0:
                    continue
                score = 1.0 - (dist / max_len)
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = choice
        else:
            if abs(w_len - len(c_clean)) > 2:
                continue
            dist = get_edit_distance(word, c_clean)
            max_len = max(w_len, len(c_clean))
            if max_len == 0:
                continue
            score = 1.0 - (dist / max_len)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = choice
    return best_match


def clean_column_names(columns):
    mapping = {
        'name': 'Name',
        'agniveer_no': 'Agniveer No',
        'bn_desp': 'Unit',
        'trade': 'Trade',
        'company': 'Company',
        'platoon': 'Platoon',
        'test_type': 'Test Type',
        'category': 'Category',
        'status': 'Status',
        'marks': 'Marks',
        'department': 'Department',
        'username': 'Username',
        'first_name': 'First Name',
        'last_name': 'Last Name',
        'role': 'Role',
        'action': 'Action',
        'description': 'Description',
        'timestamp': 'Timestamp',
        'is_active': 'Active',
    }
    cleaned = []
    for col in columns:
        clean_name = col.split('.')[-1].lower()
        cleaned.append(mapping.get(clean_name, col.replace('_', ' ').title()))
    return cleaned


def interpret_query_direct(question, mem_conn, last_intent=None, last_filters=None, user=None):
    """
    Direct natural language query compiler. Parses entities and intent, runs SQL,
    and returns response structures in milliseconds without calling local LLMs.
    """
    lexicon = extract_lexicon(mem_conn)
    q = question.lower().strip()
    # Normalize multiple whitespace characters to a single space
    q = re.sub(r'\s+', ' ', q)

    # Normalize common misspellings
    misspellings = {
        'agnoveer': 'agniveer',
        'agniver': 'agniveer',
        'agb=niveers': 'agniveer',
        'agb=niveer': 'agniveer',
        'agniveers': 'agniveer',
        'tets': 'test',
        'tst': 'test',
        'evalaution': 'evaluation',
        'evalution': 'evaluation',
        'oin': 'on',
        'ghead': 'g_head',
        'g-head': 'g_head',
        'overall': 'overall',
        'comapany': 'company',
        'comany': 'company',
        'cmpany': 'company',
        'platun': 'platoon',
        'platon': 'platoon',
        'firiug': 'firing',
        'firiu g': 'firing',
        'firig': 'firing',
        'firng': 'firing',
        'baiss': 'basis',
        'differenciate': 'differentiate',
        'wiorng': 'wrong',
        'wior': 'wrong',
        'wirong': 'wrong',
        'registerd': 'registered',
        'depatments': 'departments',
        'efficeient': 'efficient',
        'queies': 'queries',
        'thre': 'three',
        'athen': 'then',
        'meggido': 'megiddo',
        'megido': 'megiddo',
        'cassino': 'cassino',
        'maktila': 'maktila',
        'tirah': 'tirah',
        'ghuznee': 'ghuznee',
        'pigris': 'pigris',
        'cmk': 'cmk_sheet',
        'wpn': 'wpn_handling',
        'weapon handling': 'wpn_handling',
        'final exam': 'final_result',
        'final test': 'final_result',
        'final results': 'final_result',
        'overall final': 'final_result',
        'cs result': 'cs_result',
        'cs clerk': 'cs_clerk_result',
        'dmv result': 'dmv_result',
        'opem result': 'opem_result',
        'mr3': 'mr_iii',
        'mr-iii': 'mr_iii',
        'mr iii': 'mr_iii',
        'ranlers': 'rankers',
        'ranler': 'ranker',
        'ranlk': 'rank',
        'ranlks': 'rank',
        'noty': 'not',
    }
    for mis, corr in misspellings.items():
        if not mis.isalnum():
            q = q.replace(mis, corr)
        q = re.sub(r'\b' + re.escape(mis) + r'\b', corr, q)

    # Detect follow-up intent context
    is_followup = q.startswith("and ") or q.startswith("what about ") or q.startswith("how about ") or q.startswith("in ") or q.startswith("or ") or "of them" in q or q.startswith("list them") or q.startswith("show them")

    if is_followup and last_filters:
        # Clone previous filters
        filters = {k: list(v) if isinstance(v, list) else v for k, v in last_filters.items()}
    else:
        filters = {
            'companies': [],
            'platoons': [],
            'trades': [],
            'bn_desps': [],
            'statuses': [],
            'test_types': [],
            'categories': [],
            'departments': [],
            'names': [],
            'agniveer_nos': [],
            'usernames': [],
            'actions': []
        }

    exclude_filters = {
        'companies': [],
        'platoons': [],
        'trades': [],
        'bn_desps': [],
        'statuses': [],
        'test_types': []
    }

    def is_negated(pattern, text):
        matches = list(re.finditer(r'\b' + re.escape(pattern) + r'\b', text))
        if not matches:
            return False
        for m in matches:
            start = m.start()
            preceding = text[max(0, start - 30):start]
            if re.search(r'\b(not|noty|except|excluding|but|without|no)\b', preceding):
                return True
        return False

    def find_test_match_keyword(test_name, query_norm):
        test_norm = test_name.lower().replace("_", " ").replace("-", " ")
        if re.search(r'\b' + re.escape(test_norm) + r'\b', query_norm):
            return test_norm
        if test_name == 'CMK_SHEET' and re.search(r'\bcmk\b', query_norm):
            return 'cmk'
        if test_name == 'WPN_HANDLING':
            if re.search(r'\bwpn\b', query_norm):
                return 'wpn'
            if re.search(r'\bweapon\b', query_norm):
                return 'weapon'
        if test_name == 'FINAL_RESULT':
            for kw in ['overall final', 'final exam', 'final test', 'final']:
                if re.search(r'\b' + re.escape(kw) + r'\b', query_norm):
                    return kw
        return None

    # Check for difference in average score calculation
    if "difference" in q and "average" in q:
        # Find matched companies
        matched_companies = []
        for company in lexicon['companies']:
            comp_lower = company.lower()
            comp_name = comp_lower.replace("company", "").strip()
            if re.search(r'\b' + re.escape(comp_name) + r'\b', q) or re.search(r'\b' + re.escape(comp_lower) + r'\b', q):
                if company not in matched_companies:
                    matched_companies.append(company)
        
        # Find test type
        test_type = None
        for test in lexicon['test_types']:
            test_norm = test.lower().replace("_", " ").replace("-", " ")
            q_norm = q.replace("_", " ").replace("-", " ")
            if re.search(r'\b' + re.escape(test_norm) + r'\b', q_norm):
                test_type = test
                break
        if not test_type:
            for t in ['Firing', 'PPT', 'BPET', 'DST']:
                if t.lower() in q:
                    test_type = t
                    break
        
        if len(matched_companies) == 2 and test_type:
            c1, c2 = matched_companies
            cursor = mem_conn.cursor()
            avg_sql = """
                SELECT AVG(m.marks) FROM evaluation_marks m 
                JOIN evaluation_evaluationsheet s ON m.evaluation_sheet_id = s.id 
                JOIN departments_agniveer a ON s.agniveer_id = a.id 
                WHERE s.test_type = ? AND a.company = ?
            """
            cursor.execute(avg_sql, (test_type, c1))
            row1 = cursor.fetchone()
            avg1 = row1[0] if row1 and row1[0] is not None else 0
            
            cursor.execute(avg_sql, (test_type, c2))
            row2 = cursor.fetchone()
            avg2 = row2[0] if row2 and row2[0] is not None else 0
            
            diff = abs(avg1 - avg2)
            
            answer = f"The average marks in **{test_type}** is **{round(avg1, 2)}** for **{c1}** and **{round(avg2, 2)}** for **{c2}**. The difference is **{round(diff, 2)}** marks."
            mock_sql = f"""SELECT ABS(
  (SELECT AVG(m.marks) FROM evaluation_marks m JOIN evaluation_evaluationsheet s ON m.evaluation_sheet_id = s.id JOIN departments_agniveer a ON s.agniveer_id = a.id WHERE s.test_type = '{test_type}' AND a.company = '{c1}') -
  (SELECT AVG(m.marks) FROM evaluation_marks m JOIN evaluation_evaluationsheet s ON m.evaluation_sheet_id = s.id JOIN departments_agniveer a ON s.agniveer_id = a.id WHERE s.test_type = '{test_type}' AND a.company = '{c2}')
) AS average_difference;"""
            
            return {
                'success': True,
                'sql': mock_sql,
                'columns': ['Average Difference'],
                'rows': [[round(diff, 2)]],
                'answer': answer,
                'intent': 'calculation',
                'filters': {'test_types': [test_type], 'companies': matched_companies}
            }

    # Match companies
    matched_companies = []
    for company in lexicon['companies']:
        comp_lower = company.lower()
        comp_name = comp_lower.replace("company", "").strip()
        if re.search(r'\b' + re.escape(comp_name) + r'\b', q) or re.search(r'\b' + re.escape(comp_lower) + r'\b', q):
            if is_negated(comp_name, q) or is_negated(comp_lower, q):
                if company not in exclude_filters['companies']:
                    exclude_filters['companies'].append(company)
            else:
                if company not in matched_companies:
                    matched_companies.append(company)
    if matched_companies:
        filters['companies'] = matched_companies

    # Match platoons
    matched_platoons = []
    for platoon in lexicon['platoons']:
        if re.search(r'\b' + re.escape(platoon.lower()) + r'\b', q):
            if is_negated(platoon.lower(), q):
                if platoon not in exclude_filters['platoons']:
                    exclude_filters['platoons'].append(platoon)
            else:
                if platoon not in matched_platoons:
                    matched_platoons.append(platoon)
    if matched_platoons:
        filters['platoons'] = matched_platoons

    # Match trades (normalized with spaces/slashes to handle Trade inputs robustly)
    matched_trades = []
    for trade in lexicon['trades']:
        trade_norm = trade.lower().replace("_", " ").replace("-", " ").replace("/", " ").replace("&", " ")
        q_norm = q.replace("_", " ").replace("-", " ").replace("/", " ").replace("&", " ")
        if re.search(r'\b' + re.escape(trade_norm) + r'\b', q_norm):
            if is_negated(trade_norm, q_norm):
                if trade not in exclude_filters['trades']:
                    exclude_filters['trades'].append(trade)
            else:
                if trade not in matched_trades:
                    matched_trades.append(trade)
    if not matched_trades and not exclude_filters['trades']:
        if 'clerk' in q or 'clk' in q:
            is_neg = False
            for word in ['clerk', 'clk']:
                if is_negated(word, q):
                    is_neg = True
                    break
            for t in lexicon['trades']:
                if t.upper() in ['CLK', 'CLERK']:
                    if is_neg:
                        if t not in exclude_filters['trades']:
                            exclude_filters['trades'].append(t)
                    else:
                        if t not in matched_trades:
                            matched_trades.append(t)
        if 'driver' in q or 'dmv' in q:
            is_neg = False
            for word in ['driver', 'dmv']:
                if is_negated(word, q):
                    is_neg = True
                    break
            for t in lexicon['trades']:
                if t.upper() in ['DMV']:
                    if is_neg:
                        if t not in exclude_filters['trades']:
                            exclude_filters['trades'].append(t)
                    else:
                        if t not in matched_trades:
                            matched_trades.append(t)
    if matched_trades:
        filters['trades'] = matched_trades

    # Match battalion (bn_desp)
    matched_bn = []
    for bn in lexicon['battalions']:
        bn_pat = bn.lower().replace("tb", r'\s*tb')
        if re.search(r'\b' + bn_pat + r'\b', q):
            is_neg = False
            for m in re.finditer(r'\b' + bn_pat + r'\b', q):
                preceding = q[max(0, m.start() - 30):m.start()]
                if re.search(r'\b(not|noty|except|excluding|but|without|no)\b', preceding):
                    is_neg = True
                    break
            if is_neg:
                if bn not in exclude_filters['bn_desps']:
                    exclude_filters['bn_desps'].append(bn)
            else:
                if bn not in matched_bn:
                    matched_bn.append(bn)
    if matched_bn:
        filters['bn_desps'] = matched_bn

    # Match status
    status_map = {
        'active': ['active'],
        'completed': ['completed', 'complete'],
        'dropped': ['dropped', 'drop', 'dropped out'],
        'pass': ['passed', 'pass', 'passed agniveer', 'passing'],
        'fail': ['failed', 'fail', 'failed agniveer', 'failing']
    }
    matched_statuses = []
    for status, synonyms in status_map.items():
        for syn in synonyms:
            if re.search(r'\b' + re.escape(syn) + r'\b', q):
                is_neg = False
                for m in re.finditer(r'\b' + re.escape(syn) + r'\b', q):
                    preceding = q[max(0, m.start() - 30):m.start()]
                    if re.search(r'\b(not|noty|except|excluding|but|without|no)\b', preceding):
                        is_neg = True
                        break
                if is_neg:
                    if status not in exclude_filters['statuses']:
                        exclude_filters['statuses'].append(status)
                else:
                    if status not in matched_statuses:
                        matched_statuses.append(status)
                break
    if matched_statuses:
        filters['statuses'] = matched_statuses

    # Match test_type (normalized to match hyphens, spaces and underscores)
    matched_tests = []
    for test in lexicon['test_types']:
        q_norm = q.replace("_", " ").replace("-", " ")
        matched_kw = find_test_match_keyword(test, q_norm)
        if matched_kw:
            if is_negated(matched_kw, q_norm):
                if test not in exclude_filters['test_types']:
                    exclude_filters['test_types'].append(test)
            else:
                if test not in matched_tests:
                    matched_tests.append(test)
    if not matched_tests and not exclude_filters['test_types']:
        standard_tests = [
            'PPT', 'BPET', 'Firing', 'DST', 'MR_III', 'BFC', 'PDP', 'FC_All', 'CMK_SHEET', 'WPN_HANDLING', 
            'FINAL_RESULT', 'CS_RESULT', 'CS_CLERK_RESULT', 'CS_ASSESSMENT', 'CLK_FINAL', 
            'CLK_WEEKLY_1', 'CLK_WEEKLY_2', 'CLK_INITIAL', 'OPEM_ASSESSMENT', 'DMV_ASSESSMENT', 
            'OTHER_ASSESSMENT', 'DMV_RESULT', 'OPEM_RESULT', 'OTHER_SCREEN_BOARD'
        ]
        for test in standard_tests:
            q_norm = q.replace("_", " ").replace("-", " ")
            matched_kw = find_test_match_keyword(test, q_norm)
            if matched_kw:
                if is_negated(matched_kw, q_norm):
                    if test not in exclude_filters['test_types']:
                        exclude_filters['test_types'].append(test)
                else:
                    if test not in matched_tests:
                        matched_tests.append(test)
    if matched_tests:
        filters['test_types'] = matched_tests


    # Match category (normalized, excluding common stopwords like 'trade')
    matched_cats = []
    for cat in lexicon['categories']:
        if cat.lower() == 'trade':
            continue
        if re.search(r'\b' + re.escape(cat.lower()) + r'\b', q):
            if cat not in matched_cats:
                matched_cats.append(cat)
    if matched_cats:
        filters['categories'] = matched_cats

    # Match department
    dept_map = {
        'A': ['dept a', 'battalion', 'department a'],
        'B': ['dept b', 'tts', 'technical training', 'department b'],
        'C': ['dept c', 'cs', 'ces', 'communication system', 'department c'],
        'D': ['dept d', 'clerk', 'clerical', 'department d']
    }
    matched_depts = []
    for dept, synonyms in dept_map.items():
        for syn in synonyms:
            if re.search(r'\b' + re.escape(syn) + r'\b', q):
                if dept not in matched_depts:
                    matched_depts.append(dept)
                break
    if matched_depts:
        filters['departments'] = matched_depts

    # Match specific trainee name (using word boundaries to avoid partial word substring matches)
    matched_names = []
    sorted_names = sorted(lexicon['names'], key=len, reverse=True)
    for name in sorted_names:
        name_lower = name.lower()
        if re.search(r'\b' + re.escape(name_lower) + r'\b', q):
            if name not in matched_names:
                matched_names.append(name)
    if matched_names:
        filters['names'] = matched_names

    # Match specific agniveer number
    matched_nos = []
    for agn_no in lexicon['agniveer_nos']:
        if agn_no.lower() in q:
            if agn_no not in matched_nos:
                matched_nos.append(agn_no)
    if matched_nos:
        filters['agniveer_nos'] = matched_nos

    # Match username
    matched_users = []
    for username in lexicon['usernames']:
        if re.search(r'\b' + re.escape(username.lower()) + r'\b', q):
            if username not in matched_users:
                matched_users.append(username)
    if matched_users:
        filters['usernames'] = matched_users

    # Match activity log action
    matched_actions = []
    for action in lexicon['actions']:
        if re.search(r'\b' + re.escape(action.lower()) + r'\b', q):
            if action not in matched_actions:
                matched_actions.append(action)
    if matched_actions:
        filters['actions'] = matched_actions

    # Fuzzy matching search tokens (for misspelled words that failed exact matching)
    words = re.findall(r'\b[a-z]{3,}\b', q)
    fuzzy_stopwords = {
        'how', 'many', 'total', 'count', 'show', 'list', 'details', 'find', 
        'whose', 'them', 'only', 'were', 'found', 'and', 'the', 'for', 'who', 
        'user', 'in', 'is', 'of', 'on', 'at', 'by', 'with', 'from', 'to', 'or',
        'are', 'was', 'were', 'been', 'have', 'has', 'had', 'do', 'does', 'did',
        'about', 'overall', 'evaluated', 'evaluation', 'test', 'tests', 'done',
        'active', 'passed', 'failed', 'pass', 'fail', 'completed', 'dropped',
        'registered', 'admin', 'users', 'accounts', 'log', 'logs', 'action', 
        'actions', 'differentiate', 'basis', 'departments', 'department', 
        'company', 'platoon', 'trade', 'trades', 'unit', 'battalion'
    }
    for word in words:
        if word in fuzzy_stopwords:
            continue
        
        is_word_negated = is_negated(word, q)

        # Company
        if is_word_negated:
            if not exclude_filters['companies']:
                f_comp = fuzzy_match(word, lexicon['companies'], threshold=0.7, split_choices=True)
                if f_comp:
                    exclude_filters['companies'] = [f_comp]
        else:
            if not filters['companies']:
                f_comp = fuzzy_match(word, lexicon['companies'], threshold=0.7, split_choices=True)
                if f_comp:
                    filters['companies'] = [f_comp]
                
        # Test Type
        if is_word_negated:
            if not exclude_filters['test_types']:
                f_test = fuzzy_match(word, lexicon['test_types'], threshold=0.65)
                if f_test:
                    exclude_filters['test_types'] = [f_test]
        else:
            if not filters['test_types']:
                f_test = fuzzy_match(word, lexicon['test_types'], threshold=0.65)
                if f_test:
                    filters['test_types'] = [f_test]
                
        # Trade
        if is_word_negated:
            if not exclude_filters['trades']:
                f_trade = fuzzy_match(word, lexicon['trades'], threshold=0.75)
                if f_trade:
                    exclude_filters['trades'] = [f_trade]
        else:
            if not filters['trades']:
                f_trade = fuzzy_match(word, lexicon['trades'], threshold=0.75)
                if f_trade:
                    filters['trades'] = [f_trade]
                
        # Name
        if not filters['names']:
            f_name = fuzzy_match(word, lexicon['names'], threshold=0.8, split_choices=True)
            if f_name:
                filters['names'].append(f_name)

    # Match partial name searches
    name_search_match = re.search(r'\b(?:named|name is|name contains|search for)\s+([a-zA-Z0-9_\-\s]+)\b', q)
    if name_search_match and not filters['names']:
        name_val = name_search_match.group(1).strip()
        stopwords = ['contains', 'like', 'is', 'the', 'of', 'in', 'show', 'list', 'details', 'for', 'who', 'has']
        name_words = [w for w in name_val.split() if w not in stopwords]
        if name_words:
            search_term = " ".join(name_words)
            filters['name_like'] = f"%{search_term}%"

    # Match overall evaluation keyword
    if any(w in q for w in ["overall", "all evaluations", "entire", "overall evaluation"]):
        if 'FINAL_RESULT' not in filters['test_types']:
            filters['test_types'].append('FINAL_RESULT')

    # Check for pass/fail percentage calculation
    if any(w in q for w in ["pass percentage", "passing percentage", "pass rate", "fail percentage", "failing percentage", "fail rate"]):
        is_fail_rate = any(w in q for w in ["fail percentage", "failing percentage", "fail rate"])
        
        # 1. Resolve scoped trainees matching the filters
        from evaluation.result_helpers import is_sheet_evaluated, build_department_result_row
        from reports.views import scoped_agniveers, scoped_sheets
        
        user_dept = None
        if user:
            user_dept = user.get_department_code()
        target_dept = filters['departments'][0] if filters['departments'] else user_dept
        
        if user:
            agniveers_qs = scoped_agniveers(Agniveer.objects.all(), user, target_dept)
        else:
            agniveers_qs = Agniveer.objects.all()
            
        if filters['companies']:
            agniveers_qs = agniveers_qs.filter(company__in=filters['companies'])
        if filters['platoons']:
            agniveers_qs = agniveers_qs.filter(platoon__in=filters['platoons'])
        if filters['trades']:
            agniveers_qs = agniveers_qs.filter(trade__in=filters['trades'])
        if filters['bn_desps']:
            agniveers_qs = agniveers_qs.filter(bn_desp__in=filters['bn_desps'])
        if filters['names']:
            agniveers_qs = agniveers_qs.filter(name__in=filters['names'])
        if 'name_like' in filters:
            agniveers_qs = agniveers_qs.filter(name__icontains=filters['name_like'].replace("%", ""))
            
        # Apply exclude filters
        if exclude_filters['companies']:
            agniveers_qs = agniveers_qs.exclude(company__in=exclude_filters['companies'])
        if exclude_filters['platoons']:
            agniveers_qs = agniveers_qs.exclude(platoon__in=exclude_filters['platoons'])
        if exclude_filters['trades']:
            agniveers_qs = agniveers_qs.exclude(trade__in=exclude_filters['trades'])
        if exclude_filters['bn_desps']:
            agniveers_qs = agniveers_qs.exclude(bn_desp__in=exclude_filters['bn_desps'])
        if exclude_filters['statuses']:
            agniveers_qs = agniveers_qs.exclude(status__in=exclude_filters['statuses'])
            
        all_sheets = EvaluationSheet.objects.all().prefetch_related('marks')
        if target_dept and user:
            all_sheets = scoped_sheets(all_sheets, user, target_dept)
            departments = [target_dept]
        else:
            departments = [target_dept] if target_dept else ['A']
            
        passed_count = 0
        failed_count = 0
        evaluated_count = 0
        
        # If specific test type is provided (e.g. "pass percentage in PPT"), use that test type threshold
        if filters['test_types']:
            test_type = filters['test_types'][0]
            passing_thresholds = {
                'PPT': 40, 'BPET': 40, 'Firing': 40, 'DST': 40, 'MR_III': 40,
                'BFC': 96, 'PDP': 20, 'FC_All': 36, 'CMK_SHEET': 8, 'WPN_HANDLING': 8,
                'FINAL_RESULT': 48, 
                'CS_RESULT': 20, 'CS_CLERK_RESULT': 20, 'CS_ASSESSMENT': 20, 
                'CLK_FINAL': 19, 'CLK_WEEKLY_1': 69, 'CLK_WEEKLY_2': 127, 'CLK_INITIAL': 58, 
                'OPEM_ASSESSMENT': 36, 'DMV_ASSESSMENT': 36, 'OTHER_ASSESSMENT': 35, 
                'DMV_RESULT': 20, 'OPEM_RESULT': 20, 'OTHER_SCREEN_BOARD': 20
            }
            threshold = passing_thresholds.get(test_type, 40)
            
            # Query evaluating trainees and scores from memory sandbox
            cursor = mem_conn.cursor()
            # Resolve trainee IDs in scopes
            scoped_ids = list(agniveers_qs.values_list('id', flat=True))
            if scoped_ids:
                placeholders = ",".join(["?"] * len(scoped_ids))
                cursor.execute(f"""
                    SELECT m.marks FROM evaluation_marks m 
                    JOIN evaluation_evaluationsheet s ON m.evaluation_sheet_id = s.id 
                    WHERE s.test_type = ? AND s.agniveer_id IN ({placeholders})
                """, [test_type] + scoped_ids)
                marks_rows = cursor.fetchall()
                evaluated_count = len(marks_rows)
                for (mrk,) in marks_rows:
                    if mrk >= threshold:
                        passed_count += 1
                    else:
                        failed_count += 1
        else:
            # Overall pass/fail using the result helper logic
            for ag in agniveers_qs:
                total_marks = 0
                max_marks = 0
                evaluated_in_scope = False
                
                is_battalion_trainee = False
                if ag.bn_desp:
                    bn_clean = ag.bn_desp.replace(" ", "").upper()
                    if any(x in bn_clean for x in ['1TB', '2TB', '3TB', '4TB', '5TB', 'STB']):
                        is_battalion_trainee = True
                
                if is_battalion_trainee:
                    dept_sheets = [s for s in all_sheets.filter(agniveer=ag, department='A') if is_sheet_evaluated(s)]
                    evaluated_in_scope = True
                    result_row = build_department_result_row(ag, dept_sheets, 'A')
                    total_marks = result_row.get('grand_total', 0) or 0
                    max_marks = 120
                else:
                    for dept_code_eval in departments:
                        dept_sheets = [s for s in all_sheets.filter(agniveer=ag, department=dept_code_eval) if is_sheet_evaluated(s)]
                        if not dept_sheets:
                            continue
                        evaluated_in_scope = True
                        result_row = build_department_result_row(ag, dept_sheets, dept_code_eval)
                        total_marks += result_row.get('grand_total', 0) or 0
                        max_marks += result_row.get('max_total') or 40
                    
                if not evaluated_in_scope:
                    continue
                    
                percentage = (total_marks / max_marks) * 100 if max_marks > 0 else 0
                passing_threshold = 40 if 'A' in departments and len(departments) == 1 else 50
                
                evaluated_count += 1
                if percentage >= passing_threshold:
                    passed_count += 1
                else:
                    failed_count += 1
                    
        # Calculate percentage
        pct = 0.0
        if evaluated_count > 0:
            pct = (failed_count if is_fail_rate else passed_count) * 100.0 / evaluated_count
        pct_formatted = f"{round(pct, 2)}%"
            
        scope_desc_parts = []
        if filters['companies']:
            scope_desc_parts.append(filters['companies'][0])
        if filters['platoons']:
            scope_desc_parts.append(filters['platoons'][0])
        if filters['trades']:
            scope_desc_parts.append(f"{filters['trades'][0]} trade")
        if filters['bn_desps']:
            scope_desc_parts.append(filters['bn_desps'][0])
        if filters['test_types']:
            scope_desc_parts.append(filters['test_types'][0])
            
        scope_desc = f" in {' '.join(scope_desc_parts)}" if scope_desc_parts else ""
        
        term = "fail" if is_fail_rate else "pass"
        count_desc = f"({failed_count if is_fail_rate else passed_count} {term} out of {evaluated_count} evaluated)"
        answer = f"The {term} percentage{scope_desc} is **{pct_formatted}** {count_desc}."
        
        # Build mock SQL query for user transparency
        test_type_filter = f" AND s.test_type = '{filters['test_types'][0]}'" if filters['test_types'] else ""
        company_filter = f" AND a.company = '{filters['companies'][0]}'" if filters['companies'] else ""
        trade_filter = f" AND a.trade = '{filters['trades'][0]}'" if filters['trades'] else ""
        platoon_filter = f" AND a.platoon = '{filters['platoons'][0]}'" if filters['platoons'] else ""
        unit_filter = f" AND a.bn_desp = '{filters['bn_desps'][0]}'" if filters['bn_desps'] else ""
        
        exclude_companies_str = ",".join(f"'{c}'" for c in exclude_filters['companies'])
        exclude_company_filter = f" AND a.company NOT IN ({exclude_companies_str})" if exclude_filters['companies'] else ""
        
        exclude_trades_str = ",".join(f"'{t}'" for t in exclude_filters['trades'])
        exclude_trade_filter = f" AND a.trade NOT IN ({exclude_trades_str})" if exclude_filters['trades'] else ""
        
        exclude_platoons_str = ",".join(f"'{p}'" for p in exclude_filters['platoons'])
        exclude_platoon_filter = f" AND a.platoon NOT IN ({exclude_platoons_str})" if exclude_filters['platoons'] else ""
        
        exclude_units_str = ",".join(f"'{u}'" for u in exclude_filters['bn_desps'])
        exclude_unit_filter = f" AND a.bn_desp NOT IN ({exclude_units_str})" if exclude_filters['bn_desps'] else ""
        
        exclude_tests_str = ",".join(f"'{t}'" for t in exclude_filters['test_types'])
        exclude_test_filter = f" AND s.test_type NOT IN ({exclude_tests_str})" if exclude_filters['test_types'] else ""
        
        mock_sql = f"""SELECT 
  COUNT(CASE WHEN is_{term} = 1 THEN 1 END) * 100.0 / COUNT(*) AS {term}_percentage,
  COUNT(CASE WHEN is_{term} = 1 THEN 1 END) AS {term}_count,
  COUNT(*) AS total_evaluated
FROM (
  SELECT a.id, 
    -- pass/fail status is computed dynamically per department result helper criteria
    CASE WHEN a.status = '{term}' THEN 1 ELSE 0 END AS is_{term}
  FROM departments_agniveer a
  JOIN evaluation_evaluationsheet s ON a.id = s.agniveer_id
  WHERE 1=1{test_type_filter}{company_filter}{trade_filter}{platoon_filter}{unit_filter}{exclude_company_filter}{exclude_trade_filter}{exclude_platoon_filter}{exclude_unit_filter}{exclude_test_filter}
);"""
        
        return {
            'success': True,
            'sql': mock_sql,
            'columns': [f'{term.title()} Percentage', f'{term.title()} Count', 'Total Evaluated'],
            'rows': [[round(pct, 2), failed_count if is_fail_rate else passed_count, evaluated_count]],
            'answer': answer,
            'intent': 'calculation',
            'filters': filters
        }

    # Check if they are asking for report card / individual details
    has_name_or_no = bool(filters['names']) or bool(filters['agniveer_nos']) or 'name_like' in filters
    is_details_query = any(w in q for w in ["report card", "details", "reportcard", "profile", "individual details", "info", "information", "card"])
    
    if has_name_or_no and is_details_query:
        from evaluation.result_helpers import is_sheet_evaluated, build_department_result_row
        from reports.views import scoped_agniveers
        
        user_dept = None
        if user:
            user_dept = user.get_department_code()
            
        if user:
            agniveers_qs = scoped_agniveers(Agniveer.objects.all(), user, user_dept)
        else:
            agniveers_qs = Agniveer.objects.all()
            
        if filters['names']:
            agniveers_qs = agniveers_qs.filter(name__in=filters['names'])
        elif filters['agniveer_nos']:
            agniveers_qs = agniveers_qs.filter(agniveer_no__in=filters['agniveer_nos'])
        elif 'name_like' in filters:
            agniveers_qs = agniveers_qs.filter(name__icontains=filters['name_like'].replace("%", ""))
            
        ag = agniveers_qs.first()
        if ag:
            sheets = EvaluationSheet.objects.filter(agniveer=ag).prefetch_related('marks')
            
            rows = []
            passing_thresholds = {
                'PPT': 40, 'BPET': 40, 'Firing': 40, 'DST': 40, 'MR_III': 40,
                'BFC': 96, 'PDP': 20, 'FC_All': 36, 'CMK_SHEET': 8, 'WPN_HANDLING': 8,
                'FINAL_RESULT': 48, 
                'CS_RESULT': 20, 'CS_CLERK_RESULT': 20, 'CS_ASSESSMENT': 20, 
                'CLK_FINAL': 19, 'CLK_WEEKLY_1': 69, 'CLK_WEEKLY_2': 127, 'CLK_INITIAL': 58, 
                'OPEM_ASSESSMENT': 36, 'DMV_ASSESSMENT': 36, 'OTHER_ASSESSMENT': 35, 
                'DMV_RESULT': 20, 'OPEM_RESULT': 20, 'OTHER_SCREEN_BOARD': 20
            }
            
            max_marks_map = {
                'PPT': 100, 'BPET': 100, 'Firing': 100, 'DST': 100, 'MR_III': 100,
                'BFC': 240, 'PDP': 50, 'FC_All': 90, 'CMK_SHEET': 20, 'WPN_HANDLING': 20,
                'FINAL_RESULT': 120, 
                'CS_RESULT': 40, 'CS_CLERK_RESULT': 40, 'CS_ASSESSMENT': 40, 
                'CLK_FINAL': 40, 'CLK_WEEKLY_1': 150, 'CLK_WEEKLY_2': 275, 'CLK_INITIAL': 125, 
                'OPEM_ASSESSMENT': 40, 'DMV_ASSESSMENT': 40, 'OTHER_ASSESSMENT': 40, 
                'DMV_RESULT': 40, 'OPEM_RESULT': 40, 'OTHER_SCREEN_BOARD': 40
            }
            
            for sheet in sheets:
                if not is_sheet_evaluated(sheet):
                    continue
                marks_obj = sheet.marks.first()
                score = marks_obj.marks if marks_obj else 0
                max_val = max_marks_map.get(sheet.test_type, 100)
                threshold = passing_thresholds.get(sheet.test_type, 40)
                status = "PASS" if score >= threshold else "FAIL"
                
                rows.append([
                    sheet.test_type,
                    sheet.category.title(),
                    f"{score}/{max_val}",
                    f"{threshold}/{max_val}",
                    status
                ])
                
            columns = ['Test Type', 'Category', 'Score Obtained', 'Passing Marks', 'Status']
            
            departments = ['A', 'B', 'C', 'D']
            dept_sheets_map = {}
            for s in sheets:
                if is_sheet_evaluated(s):
                    dept_sheets_map.setdefault(s.department, []).append(s)
                    
            summary_parts = []
            for d in departments:
                d_sheets = dept_sheets_map.get(d, [])
                if d_sheets:
                    res_row = build_department_result_row(ag, d_sheets, d)
                    pct = res_row.get('percentage', 0)
                    pass_str = "PASS" if res_row.get('is_pass') else "FAIL"
                    summary_parts.append(f"Dept {d}: **{pct}% ({pass_str})**")
                    
            summary_str = " | ".join(summary_parts) if summary_parts else "No overall results compiled."
            
            answer = f"**Report Card for {ag.name}** ({ag.agniveer_no or ag.enrollment_number})<br>"
            answer += f"**Unit**: {ag.bn_desp or 'N/A'} | **Company**: {ag.company or 'N/A'} | **Platoon**: {ag.platoon or 'N/A'} | **Trade**: {ag.trade or 'N/A'}<br>"
            answer += f"**Overall Performance**: {summary_str}"
            
            mock_sql = f"""SELECT s.test_type, s.category, m.marks 
FROM evaluation_evaluationsheet s 
JOIN evaluation_marks m ON m.evaluation_sheet_id = s.id 
WHERE s.agniveer_id = {ag.id};"""
            
            return {
                'success': True,
                'sql': mock_sql,
                'columns': columns,
                'rows': rows,
                'answer': answer,
                'intent': 'list',
                'filters': filters
            }

    # Check for rankings queries (overall, final exam, or department-wise)
    is_ranking_query = any(w in q for w in ["rank", "top", "best", "first", "1st", "performer", "performers", "lowest", "bottom", "worst", "final exam", "overall"])
    if is_ranking_query:
        # Determine top N limit
        limit_num = 10
        limit_match = re.search(r'\b(top|bottom|list|first|last|show|get)\s+(\d+)\b', q)
        if limit_match:
            limit_num = int(limit_match.group(2))
        else:
            numbers = [int(n) for n in re.findall(r'\b\d+\b', q)]
            for num in numbers:
                if 1 <= num <= 100:
                    limit_num = num
                    break
        if "first" in q or "1st" in q or "top ranker" in q or "highest" in q:
            limit_num = 1
            
        from evaluation.result_helpers import is_sheet_evaluated, build_department_result_row
        from reports.views import scoped_agniveers, scoped_sheets
        
        user_dept = None
        if user:
            user_dept = user.get_department_code()
            
        target_depts = []
        if filters['departments']:
            target_depts = filters['departments']
        elif user and user.can_view_all:
            target_depts = ['A', 'B', 'C', 'D']
        elif user_dept:
            target_depts = [user_dept]
        else:
            target_depts = ['A', 'B', 'C', 'D']
            
        if user:
            agniveers_qs = scoped_agniveers(Agniveer.objects.all(), user, target_depts[0] if len(target_depts) == 1 else None)
        else:
            agniveers_qs = Agniveer.objects.all()
            
        if filters['companies']:
            agniveers_qs = agniveers_qs.filter(company__in=filters['companies'])
        if filters['platoons']:
            agniveers_qs = agniveers_qs.filter(platoon__in=filters['platoons'])
        if filters['trades']:
            agniveers_qs = agniveers_qs.filter(trade__in=filters['trades'])
        if filters['bn_desps']:
            agniveers_qs = agniveers_qs.filter(bn_desp__in=filters['bn_desps'])
        if filters['names']:
            agniveers_qs = agniveers_qs.filter(name__in=filters['names'])
        if 'name_like' in filters:
            agniveers_qs = agniveers_qs.filter(name__icontains=filters['name_like'].replace("%", ""))
            
        # Apply exclude filters
        if exclude_filters['companies']:
            agniveers_qs = agniveers_qs.exclude(company__in=exclude_filters['companies'])
        if exclude_filters['platoons']:
            agniveers_qs = agniveers_qs.exclude(platoon__in=exclude_filters['platoons'])
        if exclude_filters['trades']:
            agniveers_qs = agniveers_qs.exclude(trade__in=exclude_filters['trades'])
        if exclude_filters['bn_desps']:
            agniveers_qs = agniveers_qs.exclude(bn_desp__in=exclude_filters['bn_desps'])
        if exclude_filters['statuses']:
            agniveers_qs = agniveers_qs.exclude(status__in=exclude_filters['statuses'])
            
        agniveers_qs = agniveers_qs.exclude(name=None).exclude(name='').exclude(name='N/A')
        
        has_test_filter = bool(filters['test_types'])
        test_type = filters['test_types'][0] if has_test_filter else None
        
        if test_type and test_type != 'FINAL_RESULT':
            cursor = mem_conn.cursor()
            scoped_ids = list(agniveers_qs.values_list('id', flat=True))
            if not scoped_ids:
                return {
                    'success': True,
                    'sql': '',
                    'columns': ['Name', 'Agniveer No', 'Unit', 'Trade', 'Company', 'Platoon', 'Test Type', 'Marks'],
                    'rows': [],
                    'answer': 'No evaluated records found matching the criteria.',
                    'intent': 'list',
                    'filters': filters
                }
            placeholders = ",".join(["?"] * len(scoped_ids))
            sql = f"""
                SELECT a.name, a.agniveer_no, a.bn_desp, a.trade, a.company, a.platoon, s.test_type, m.marks 
                FROM evaluation_marks m 
                JOIN evaluation_evaluationsheet s ON m.evaluation_sheet_id = s.id 
                JOIN departments_agniveer a ON s.agniveer_id = a.id 
                WHERE s.test_type = ? AND a.id IN ({placeholders})
                ORDER BY m.marks {"DESC" if "bottom" not in q and "lowest" not in q and "worst" not in q else "ASC"}
                LIMIT {limit_num}
            """
            cursor.execute(sql, [test_type] + scoped_ids)
            rows = cursor.fetchall()
            col_names = ['name', 'agniveer_no', 'bn_desp', 'trade', 'company', 'platoon', 'test_type', 'marks']
            cleaned_cols = clean_column_names(col_names)
            
            reverse_sort = ("bottom" not in q and "lowest" not in q and "worst" not in q)
            term = "top ranker" if reverse_sort else "bottom performer"
            if rows:
                if limit_num == 1:
                    answer = f"The {term} in **{test_type}** is **{rows[0][0]}** ({rows[0][4]}, {rows[0][5]}) with **{rows[0][7]}** marks."
                else:
                    answer = f"Here are the {term}s (top {limit_num}) in **{test_type}**:"
            else:
                answer = f"No evaluated records found for test {test_type}."
                
            return {
                'success': True,
                'sql': interpolate_sql_for_display(sql, [test_type] + scoped_ids),
                'columns': cleaned_cols,
                'rows': [list(r) for r in rows],
                'answer': answer,
                'intent': 'list',
                'filters': filters
            }
        else:
            all_sheets = EvaluationSheet.objects.all().prefetch_related('marks')
            all_sheets = all_sheets.filter(agniveer__in=agniveers_qs)
            
            trainee_results = []
            for ag in agniveers_qs:
                ag_sheets = [s for s in all_sheets.filter(agniveer=ag) if is_sheet_evaluated(s)]
                if not ag_sheets:
                    continue
                    
                dept_sheets_map = {}
                for s in ag_sheets:
                    dept_sheets_map.setdefault(s.department, []).append(s)
                    
                total_grand_total = 0.0
                total_max_total = 0.0
                evaluated_in_scope = False
                
                is_battalion_trainee = False
                if ag.bn_desp:
                    bn_clean = ag.bn_desp.replace(" ", "").upper()
                    if any(x in bn_clean for x in ['1TB', '2TB', '3TB', '4TB', '5TB', 'STB']):
                        is_battalion_trainee = True
                
                if is_battalion_trainee:
                    dept_s = dept_sheets_map.get('A', [])
                    evaluated_in_scope = True
                    res_row = build_department_result_row(ag, dept_s, 'A')
                    total_grand_total = res_row.get('grand_total', 0) or 0
                    total_max_total = 120
                else:
                    for dept_code in target_depts:
                        dept_s = dept_sheets_map.get(dept_code, [])
                        if not dept_s:
                            continue
                        evaluated_in_scope = True
                        res_row = build_department_result_row(ag, dept_s, dept_code)
                        total_grand_total += res_row.get('grand_total', 0) or 0
                        total_max_total += res_row.get('max_total') or 40
                    
                if not evaluated_in_scope:
                    continue
                    
                pct = (total_grand_total / total_max_total) * 100 if total_max_total > 0 else 0
                trainee_results.append({
                    'name': ag.get_full_name(),
                    'agniveer_no': ag.agniveer_no or ag.enrollment_number,
                    'bn_desp': ag.bn_desp or '',
                    'trade': ag.trade or '',
                    'company': ag.company or '',
                    'platoon': ag.platoon or '',
                    'grand_total': round(total_grand_total, 2),
                    'max_total': total_max_total,
                    'percentage': round(pct, 2)
                })
                
            reverse_sort = ("bottom" not in q and "lowest" not in q and "worst" not in q)
            trainee_results.sort(key=lambda x: x['percentage'], reverse=reverse_sort)
            
            top_results = trainee_results[:limit_num]
            rows = []
            for r in top_results:
                rows.append([
                    r['name'], r['agniveer_no'], r['bn_desp'], r['trade'], r['company'], r['platoon'],
                    f"{r['percentage']}%", f"{r['grand_total']}/{int(r['max_total'])}"
                ])
                
            columns = ['Name', 'Agniveer No', 'Unit', 'Trade', 'Company', 'Platoon', 'Percentage', 'Grand Total']
            
            dept_ids_str = ",".join(f"'{d}'" for d in target_depts)
            dept_filter_str = f" AND s.department IN ({dept_ids_str})" if target_depts else ""
            company_filter = f" AND a.company = '{filters['companies'][0]}'" if filters['companies'] else ""
            trade_filter = f" AND a.trade = '{filters['trades'][0]}'" if filters['trades'] else ""
            platoon_filter = f" AND a.platoon = '{filters['platoons'][0]}'" if filters['platoons'] else ""
            unit_filter = f" AND a.bn_desp = '{filters['bn_desps'][0]}'" if filters['bn_desps'] else ""
            
            exclude_companies_str = ",".join(f"'{c}'" for c in exclude_filters['companies'])
            exclude_company_filter = f" AND a.company NOT IN ({exclude_companies_str})" if exclude_filters['companies'] else ""
            
            exclude_trades_str = ",".join(f"'{t}'" for t in exclude_filters['trades'])
            exclude_trade_filter = f" AND a.trade NOT IN ({exclude_trades_str})" if exclude_filters['trades'] else ""
            
            exclude_platoons_str = ",".join(f"'{p}'" for p in exclude_filters['platoons'])
            exclude_platoon_filter = f" AND a.platoon NOT IN ({exclude_platoons_str})" if exclude_filters['platoons'] else ""
            
            exclude_units_str = ",".join(f"'{u}'" for u in exclude_filters['bn_desps'])
            exclude_unit_filter = f" AND a.bn_desp NOT IN ({exclude_units_str})" if exclude_filters['bn_desps'] else ""
            
            mock_sql = f"""SELECT a.name, a.agniveer_no, a.bn_desp, a.trade, a.company, a.platoon,
  percentage, grand_total
FROM departments_agniveer a
JOIN evaluation_evaluationsheet s ON a.id = s.agniveer_id
WHERE 1=1{dept_filter_str}{company_filter}{trade_filter}{platoon_filter}{unit_filter}{exclude_company_filter}{exclude_trade_filter}{exclude_platoon_filter}{exclude_unit_filter}
ORDER BY percentage {"DESC" if reverse_sort else "ASC"}
LIMIT {limit_num};"""
            
            scope_parts = []
            if target_depts and len(target_depts) < 4:
                scope_parts.append(f"in Department {', '.join(target_depts)}")
            if filters['companies']:
                scope_parts.append(f"in {filters['companies'][0]}")
            if filters['bn_desps']:
                scope_parts.append(f"in {filters['bn_desps'][0]}")
            if filters['trades']:
                scope_parts.append(f"in {filters['trades'][0]} trade")
                
            exclude_parts = []
            if exclude_filters['companies']:
                exclude_parts.append(f"not in {', '.join(exclude_filters['companies'])}")
            if exclude_filters['trades']:
                exclude_parts.append(f"not in {', '.join(exclude_filters['trades'])} trade")
            if exclude_filters['bn_desps']:
                exclude_parts.append(f"not in {', '.join(exclude_filters['bn_desps'])}")
            if exclude_parts:
                scope_parts.append("but " + " and ".join(exclude_parts))
                
            scope_desc = " " + ", ".join(scope_parts) if scope_parts else ""
            
            term = "top ranker" if reverse_sort else "bottom performer"
            if top_results:
                if limit_num == 1:
                    answer = f"The {term}{scope_desc} is **{top_results[0]['name']}** ({top_results[0]['company']}, {top_results[0]['platoon']}) with **{top_results[0]['percentage']}%** marks."
                else:
                    answer = f"Here are the {term}s (top {limit_num}){scope_desc}:"
            else:
                answer = f"No evaluated records found{scope_desc}."
                
            return {
                'success': True,
                'sql': mock_sql,
                'columns': columns,
                'rows': rows,
                'answer': answer,
                'intent': 'list',
                'filters': filters
            }

    # Identify intent
    intent = None
    group_by_field = None

    if any(w in q for w in ["differentiate", "group by", "breakdown", "on basis of", "split by", "by department", "differenciate"]):
        intent = 'groupby'
        if "department" in q or "dept" in q:
            group_by_field = "department"
        elif "company" in q:
            group_by_field = "company"
        elif "trade" in q:
            group_by_field = "trade"
        elif "status" in q:
            group_by_field = "status"
        elif "unit" in q or "battalion" in q or "bn" in q:
            group_by_field = "bn_desp"
        elif "platoon" in q:
            group_by_field = "platoon"
    elif any(word in q for word in ["how many", "count of", "number of", "total", "count"]):
        intent = 'count'
    elif any(word in q for word in ["average", "avg", "mean"]):
        intent = 'average'
    elif any(word in q for word in ["highest", "top", "best", "first", "1st", "first", "rank 1", "rank 1st", "maximum", "max"]):
        intent = 'max'
    elif any(word in q for word in ["lowest", "bottom", "worst", "minimum", "min"]):
        intent = 'min'
    elif any(word in q for word in ["activity log", "logs", "actions", "audit log", "audit trail"]):
        intent = 'logs'
    elif any(word in q for word in ["users", "accounts", "user list", "all users"]):
        intent = 'users'
    elif any(word in q for word in ["list", "show", "get", "find", "who", "display", "names"]):
        intent = 'list'

    if intent is None:
        if is_followup and last_intent:
            intent = last_intent
        elif any(filters.values()):
            intent = 'list'
        else:
            return {'success': False, 'reason': 'unrecognized intent and filters'}

    # Determine limits
    limit_num = 10
    if intent in ['max', 'min']:
        limit_num = 1
    limit_match = re.search(r'\b(top|bottom|list|first|last|show|get)\s+(\d+)\b', q)
    if limit_match:
        limit_num = int(limit_match.group(2))
    else:
        numbers = [int(n) for n in re.findall(r'\b\d+\b', q)]
        for num in numbers:
            if 1 <= num <= 100:
                limit_num = num
                break

    # Determine table scopes
    has_evaluated_keyword = any(w in q for w in ["evaluated", "evaluation done", "test done", "tests done"])

    has_pass = 'pass' in filters['statuses']
    has_fail = 'fail' in filters['statuses']

    need_marks = (intent in ['average', 'max', 'min']) or any(w in q for w in ['marks', 'score', 'scores', 'result', 'results', 'detail', 'details', 'show']) or ((has_pass or has_fail) and bool(filters['test_types'])) or bool(filters['names']) or 'name_like' in filters
    need_sheet = need_marks or (any(filters[f] for f in ['test_types', 'categories']) or (filters['departments'] and not (has_pass or has_fail))) or has_evaluated_keyword
    need_logs = (intent == 'logs') or bool(filters['actions']) or any(w in q for w in ['log', 'logs', 'audit'])
    need_users = (intent == 'users') or bool(filters['usernames']) or any(w in q for w in ['user', 'users', 'account', 'accounts'])

    where_clauses = []
    params = []

    def add_in_filter(column, values):
        if not values:
            return
        if len(values) == 1:
            where_clauses.append(f"{column} = ?")
            params.append(values[0])
        else:
            placeholders = ",".join(["?"] * len(values))
            where_clauses.append(f"{column} IN ({placeholders})")
            params.extend(values)

    if need_logs:
        from_clause = "logs_activitylog l JOIN accounts_customuser u ON l.user_id = u.id"
        if intent == 'count':
            select_clause = "SELECT COUNT(*)"
        else:
            select_clause = "SELECT u.username, l.role, l.action, l.description, l.timestamp"

        add_in_filter("u.username", filters['usernames'])
        add_in_filter("l.action", filters['actions'])

        order_by_clause = "ORDER BY l.timestamp DESC"
        limit_clause = f"LIMIT {limit_num}"

    elif need_users:
        from_clause = "accounts_customuser u"
        if intent == 'count':
            select_clause = "SELECT COUNT(*)"
        else:
            select_clause = "SELECT u.username, u.first_name, u.last_name, u.role, u.department, u.is_active"

        add_in_filter("u.username", filters['usernames'])

        order_by_clause = "ORDER BY u.username ASC"
        limit_clause = f"LIMIT {limit_num}"

    elif intent == 'groupby':
        if group_by_field == 'department':
            from_clause = "evaluation_evaluationsheet s JOIN departments_agniveer a ON s.agniveer_id = a.id"
            select_clause = "SELECT s.department, COUNT(DISTINCT a.id)"
            group_by_clause = "GROUP BY s.department"
        elif group_by_field:
            from_clause = "departments_agniveer a"
            select_clause = f"SELECT a.{group_by_field}, COUNT(*)"
            group_by_clause = f"GROUP BY a.{group_by_field}"
        else:
            from_clause = "departments_agniveer a"
            select_clause = "SELECT a.company, COUNT(*)"
            group_by_clause = "GROUP BY a.company"
            group_by_field = "company"

        add_in_filter("a.company", filters['companies'])
        add_in_filter("a.platoon", filters['platoons'])
        add_in_filter("a.trade", filters['trades'])
        add_in_filter("a.bn_desp", filters['bn_desps'])
        add_in_filter("a.name", filters['names'])
        add_in_filter("a.agniveer_no", filters['agniveer_nos'])
        add_in_filter("a.status", filters['statuses'])

        if 'name_like' in filters:
            where_clauses.append("a.name LIKE ?")
            params.append(filters['name_like'])

        if group_by_field == 'department':
            add_in_filter("s.category", filters['categories'])
            add_in_filter("s.test_type", filters['test_types'])

        order_by_clause = "ORDER BY COUNT(*) DESC"
        limit_clause = ""

    else:
        # Agniveer mappings
        if need_marks:
            from_clause = "evaluation_marks m JOIN evaluation_evaluationsheet s ON m.evaluation_sheet_id = s.id JOIN departments_agniveer a ON s.agniveer_id = a.id"
            if intent == 'count':
                select_clause = "SELECT COUNT(DISTINCT a.id)"
            elif intent == 'average':
                select_clause = "SELECT AVG(m.marks)"
            else:
                select_clause = "SELECT a.name, a.agniveer_no, a.bn_desp, a.trade, a.company, a.platoon, s.test_type, m.marks"
        elif need_sheet:
            from_clause = "evaluation_evaluationsheet s JOIN departments_agniveer a ON s.agniveer_id = a.id"
            if intent == 'count':
                if any(w in q for w in ["evaluation done", "evaluations done", "test done", "tests done", "evaluations", "tests"]):
                    select_clause = "SELECT COUNT(s.id)"
                else:
                    select_clause = "SELECT COUNT(DISTINCT a.id)"
            else:
                select_clause = "SELECT a.name, a.agniveer_no, a.bn_desp, a.trade, a.company, a.platoon, s.test_type, s.category, a.status"
        else:
            from_clause = "departments_agniveer a"
            if intent == 'count':
                select_clause = "SELECT COUNT(*)"
            else:
                select_clause = "SELECT a.name, a.agniveer_no, a.trade, a.bn_desp, a.company, a.platoon, a.status"

        # Apply standard filters
        add_in_filter("a.company", filters['companies'])
        add_in_filter("a.platoon", filters['platoons'])
        add_in_filter("a.trade", filters['trades'])
        add_in_filter("a.bn_desp", filters['bn_desps'])
        add_in_filter("a.name", filters['names'])
        add_in_filter("a.agniveer_no", filters['agniveer_nos'])

        def add_exclude_filter(column, values):
            if not values:
                return
            if len(values) == 1:
                where_clauses.append(f"{column} != ?")
                params.append(values[0])
            else:
                placeholders = ",".join(["?"] * len(values))
                where_clauses.append(f"{column} NOT IN ({placeholders})")
                params.extend(values)

        add_exclude_filter("a.company", exclude_filters['companies'])
        add_exclude_filter("a.platoon", exclude_filters['platoons'])
        add_exclude_filter("a.trade", exclude_filters['trades'])
        add_exclude_filter("a.bn_desp", exclude_filters['bn_desps'])
        add_exclude_filter("a.status", exclude_filters['statuses'])
        add_exclude_filter("s.test_type", exclude_filters['test_types'] if need_sheet else [])

        if 'name_like' in filters:
            where_clauses.append("a.name LIKE ?")
            params.append(filters['name_like'])

        # Exclude blank names by default for lists to keep output clean and structured
        if intent in ['list', 'show', 'max', 'min'] and not filters['names'] and 'name_like' not in filters:
            where_clauses.append("a.name IS NOT NULL AND a.name != '' AND a.name != 'N/A'")

        if need_sheet:
            add_in_filter("s.category", filters['categories'])
            add_in_filter("s.department", filters['departments'])

            # Smart test type and pass/fail condition matching
            passing_thresholds = {
                'PPT': 40, 'BPET': 40, 'Firing': 40, 'DST': 40, 'MR_III': 40,
                'BFC': 96, 'PDP': 20, 'FC_All': 36, 'CMK_SHEET': 8, 'WPN_HANDLING': 8,
                'FINAL_RESULT': 48, 
                'CS_RESULT': 20, 'CS_CLERK_RESULT': 20, 'CS_ASSESSMENT': 20, 
                'CLK_FINAL': 19, 'CLK_WEEKLY_1': 69, 'CLK_WEEKLY_2': 127, 'CLK_INITIAL': 58, 
                'OPEM_ASSESSMENT': 36, 'DMV_ASSESSMENT': 36, 'OTHER_ASSESSMENT': 35, 
                'DMV_RESULT': 20, 'OPEM_RESULT': 20, 'OTHER_SCREEN_BOARD': 20
            }

            if has_pass or has_fail:
                if filters['test_types']:
                    add_in_filter("s.test_type", filters['test_types'])
                    sub_clauses = []
                    for test_type in filters['test_types']:
                        threshold = passing_thresholds.get(test_type, 40)
                        if has_pass:
                            sub_clauses.append(f"(s.test_type = '{test_type}' AND m.marks >= {threshold})")
                        else:
                            sub_clauses.append(f"(s.test_type = '{test_type}' AND m.marks < {threshold})")
                    if sub_clauses:
                        where_clauses.append("(" + " OR ".join(sub_clauses) + ")")
                else:
                    # Dynamically compute passed/failed trainee IDs matching the dashboard business logic
                    from evaluation.result_helpers import is_sheet_evaluated, build_department_result_row
                    from reports.views import scoped_agniveers, scoped_sheets
                    
                    user_dept = None
                    if user:
                        user_dept = user.get_department_code()
                    target_dept = filters['departments'][0] if filters['departments'] else user_dept
                    
                    if user:
                        agniveers_qs = scoped_agniveers(Agniveer.objects.all(), user, target_dept)
                    else:
                        agniveers_qs = Agniveer.objects.all()
                        
                    if filters['companies']:
                        agniveers_qs = agniveers_qs.filter(company__in=filters['companies'])
                    if filters['platoons']:
                        agniveers_qs = agniveers_qs.filter(platoon__in=filters['platoons'])
                    if filters['trades']:
                        agniveers_qs = agniveers_qs.filter(trade__in=filters['trades'])
                    if filters['bn_desps']:
                        agniveers_qs = agniveers_qs.filter(bn_desp__in=filters['bn_desps'])
                    if filters['names']:
                        agniveers_qs = agniveers_qs.filter(name__in=filters['names'])
                    if 'name_like' in filters:
                        agniveers_qs = agniveers_qs.filter(name__icontains=filters['name_like'].replace("%", ""))
                        
                    # Apply exclude filters
                    if exclude_filters['companies']:
                        agniveers_qs = agniveers_qs.exclude(company__in=exclude_filters['companies'])
                    if exclude_filters['platoons']:
                        agniveers_qs = agniveers_qs.exclude(platoon__in=exclude_filters['platoons'])
                    if exclude_filters['trades']:
                        agniveers_qs = agniveers_qs.exclude(trade__in=exclude_filters['trades'])
                    if exclude_filters['bn_desps']:
                        agniveers_qs = agniveers_qs.exclude(bn_desp__in=exclude_filters['bn_desps'])
                    if exclude_filters['statuses']:
                        agniveers_qs = agniveers_qs.exclude(status__in=exclude_filters['statuses'])
                        
                    all_sheets = EvaluationSheet.objects.all().prefetch_related('marks')
                    if target_dept and user:
                        all_sheets = scoped_sheets(all_sheets, user, target_dept)
                        departments = [target_dept]
                    else:
                        departments = [target_dept] if target_dept else ['A']
                        
                    match_ids = []
                    for ag in agniveers_qs:
                        total_marks = 0
                        max_marks = 0
                        evaluated_in_scope = False
                        
                        is_battalion_trainee = False
                        if ag.bn_desp:
                            bn_clean = ag.bn_desp.replace(" ", "").upper()
                            if any(x in bn_clean for x in ['1TB', '2TB', '3TB', '4TB', '5TB', 'STB']):
                                is_battalion_trainee = True
                        
                        if is_battalion_trainee:
                            dept_sheets = [s for s in all_sheets.filter(agniveer=ag, department='A') if is_sheet_evaluated(s)]
                            evaluated_in_scope = True
                            result_row = build_department_result_row(ag, dept_sheets, 'A')
                            total_marks = result_row.get('grand_total', 0) or 0
                            max_marks = 120
                        else:
                            for dept_code_eval in departments:
                                dept_sheets = [s for s in all_sheets.filter(agniveer=ag, department=dept_code_eval) if is_sheet_evaluated(s)]
                                if not dept_sheets:
                                    continue
                                evaluated_in_scope = True
                                result_row = build_department_result_row(ag, dept_sheets, dept_code_eval)
                                total_marks += result_row.get('grand_total', 0) or 0
                                max_marks += result_row.get('max_total') or 40
                            
                        if not evaluated_in_scope:
                            continue
                            
                        percentage = (total_marks / max_marks) * 100 if max_marks > 0 else 0
                        passing_threshold = 40 if 'A' in departments and len(departments) == 1 else 50
                        
                        is_pass_status = percentage >= passing_threshold
                        if has_pass and is_pass_status:
                            match_ids.append(ag.id)
                        elif has_fail and not is_pass_status:
                            match_ids.append(ag.id)
                            
                    if match_ids:
                        placeholders = ",".join(["?"] * len(match_ids))
                        where_clauses.append(f"a.id IN ({placeholders})")
                        params.extend(match_ids)
                    else:
                        where_clauses.append("a.id IN (-1)")
            else:
                add_in_filter("s.test_type", filters['test_types'])

            remaining_statuses = [s for s in filters['statuses'] if s not in ['pass', 'fail']]
            add_in_filter("a.status", remaining_statuses)
        else:
            if (has_pass or has_fail) and not filters['test_types']:
                # Dynamically compute passed/failed trainee IDs matching the dashboard business logic
                from evaluation.result_helpers import is_sheet_evaluated, build_department_result_row
                from reports.views import scoped_agniveers, scoped_sheets
                
                user_dept = None
                if user:
                    user_dept = user.get_department_code()
                target_dept = filters['departments'][0] if filters['departments'] else user_dept
                
                if user:
                    agniveers_qs = scoped_agniveers(Agniveer.objects.all(), user, target_dept)
                else:
                    agniveers_qs = Agniveer.objects.all()
                    
                if filters['companies']:
                    agniveers_qs = agniveers_qs.filter(company__in=filters['companies'])
                if filters['platoons']:
                    agniveers_qs = agniveers_qs.filter(platoon__in=filters['platoons'])
                if filters['trades']:
                    agniveers_qs = agniveers_qs.filter(trade__in=filters['trades'])
                if filters['bn_desps']:
                    agniveers_qs = agniveers_qs.filter(bn_desp__in=filters['bn_desps'])
                if filters['names']:
                    agniveers_qs = agniveers_qs.filter(name__in=filters['names'])
                if 'name_like' in filters:
                    agniveers_qs = agniveers_qs.filter(name__icontains=filters['name_like'].replace("%", ""))
                    
                # Apply exclude filters
                if exclude_filters['companies']:
                    agniveers_qs = agniveers_qs.exclude(company__in=exclude_filters['companies'])
                if exclude_filters['platoons']:
                    agniveers_qs = agniveers_qs.exclude(platoon__in=exclude_filters['platoons'])
                if exclude_filters['trades']:
                    agniveers_qs = agniveers_qs.exclude(trade__in=exclude_filters['trades'])
                if exclude_filters['bn_desps']:
                    agniveers_qs = agniveers_qs.exclude(bn_desp__in=exclude_filters['bn_desps'])
                if exclude_filters['statuses']:
                    agniveers_qs = agniveers_qs.exclude(status__in=exclude_filters['statuses'])
                    
                all_sheets = EvaluationSheet.objects.all().prefetch_related('marks')
                if target_dept and user:
                    all_sheets = scoped_sheets(all_sheets, user, target_dept)
                    departments = [target_dept]
                else:
                    departments = [target_dept] if target_dept else ['A']
                    
                match_ids = []
                for ag in agniveers_qs:
                    total_marks = 0
                    max_marks = 0
                    evaluated_in_scope = False
                    
                    is_battalion_trainee = False
                    if ag.bn_desp:
                        bn_clean = ag.bn_desp.replace(" ", "").upper()
                        if any(x in bn_clean for x in ['1TB', '2TB', '3TB', '4TB', '5TB', 'STB']):
                            is_battalion_trainee = True
                    
                    if is_battalion_trainee:
                        dept_sheets = [s for s in all_sheets.filter(agniveer=ag, department='A') if is_sheet_evaluated(s)]
                        evaluated_in_scope = True
                        result_row = build_department_result_row(ag, dept_sheets, 'A')
                        total_marks = result_row.get('grand_total', 0) or 0
                        max_marks = 120
                    else:
                        for dept_code_eval in departments:
                            dept_sheets = [s for s in all_sheets.filter(agniveer=ag, department=dept_code_eval) if is_sheet_evaluated(s)]
                            if not dept_sheets:
                                continue
                            evaluated_in_scope = True
                            result_row = build_department_result_row(ag, dept_sheets, dept_code_eval)
                            total_marks += result_row.get('grand_total', 0) or 0
                            max_marks += result_row.get('max_total') or 40
                        
                    if not evaluated_in_scope:
                        continue
                        
                    percentage = (total_marks / max_marks) * 100 if max_marks > 0 else 0
                    passing_threshold = 40 if 'A' in departments and len(departments) == 1 else 50
                    
                    is_pass_status = percentage >= passing_threshold
                    if has_pass and is_pass_status:
                        match_ids.append(ag.id)
                    elif has_fail and not is_pass_status:
                        match_ids.append(ag.id)
                        
                if match_ids:
                    placeholders = ",".join(["?"] * len(match_ids))
                    where_clauses.append(f"a.id IN ({placeholders})")
                    params.extend(match_ids)
                else:
                    where_clauses.append("a.id IN (-1)")
            else:
                add_in_filter("a.status", filters['statuses'])

        # Ordering & limits
        order_by_clause = ""
        limit_clause = ""

        if intent == 'max':
            if need_marks:
                order_by_clause = "ORDER BY m.marks DESC"
            else:
                order_by_clause = "ORDER BY a.name ASC"
            limit_clause = f"LIMIT {limit_num}"
        elif intent == 'min':
            if need_marks:
                order_by_clause = "ORDER BY m.marks ASC"
            else:
                order_by_clause = "ORDER BY a.name ASC"
            limit_clause = f"LIMIT {limit_num}"
        elif intent in ['list', 'show']:
            if need_marks:
                order_by_clause = "ORDER BY m.marks DESC"
            else:
                order_by_clause = "ORDER BY a.name ASC"
            limit_clause = f"LIMIT {limit_num}"

    where_str = ""
    if where_clauses:
        where_str = "WHERE " + " AND ".join(where_clauses)

    if intent == 'groupby':
        sql_parts = [select_clause, "FROM", from_clause, where_str, group_by_clause, order_by_clause]
    else:
        sql_parts = [select_clause, "FROM", from_clause, where_str, order_by_clause, limit_clause]
    sql = " ".join([p for p in sql_parts if p.strip()]) + ";"

    try:
        col_names, rows = execute_sandboxed_query(mem_conn, sql, params)
    except Exception as e:
        return {'success': False, 'reason': f"SQL execution error: {str(e)}", 'sql': sql}

    display_sql = interpolate_sql_for_display(sql, params)
    
    # Format filters for response
    formatted_filters = {}
    for k, v in filters.items():
        if v:
            formatted_filters[k] = v[0] if isinstance(v, list) else v

    answer = format_direct_response_nl(question, display_sql, col_names, rows, formatted_filters, intent, limit_num)

    formatted_rows = [list(row) for row in rows]

    cleaned_cols = clean_column_names(col_names)

    return {
        'success': True,
        'sql': display_sql,
        'columns': cleaned_cols,
        'rows': formatted_rows,
        'answer': answer,
        'intent': intent,
        'filters': filters
    }
