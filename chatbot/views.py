import json
import urllib.request
from django.shortcuts import render
from django.views import View
from django.http import JsonResponse
from accounts.mixins import CommanderOrDeptMixin
from logs.utils import log_action
from .services import (
    get_sandboxed_db,
    generate_sql_from_question,
    validate_sql_query,
    execute_sandboxed_query,
    generate_friendly_answer,
    interpret_query_direct
)


class ChatbotView(CommanderOrDeptMixin, View):
    """
    Renders the premium Chatbot UI interface.
    """
    template_name = 'chatbot/chatbot.html'

    def get(self, request):
        return render(request, self.template_name)


class ChatbotQueryApiView(CommanderOrDeptMixin, View):
    """
    Endpoint that processes user's natural language questions.
    """
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Check for session reset action
            if data.get('action') == 'reset':
                request.session.pop('last_chatbot_intent', None)
                request.session.pop('last_chatbot_filters', None)
                return JsonResponse({'success': True, 'message': 'Chatbot session reset successfully.'})

            question = data.get('question', '').strip()
            model = data.get('model', 'Mistral:latest').strip()

            if not question:
                return JsonResponse({'success': False, 'error': 'Question cannot be empty.'}, status=400)

            # 1. Create a filtered sandboxed in-memory SQLite database
            mem_conn = get_sandboxed_db(request.user)

            sql = ""
            error_msg = ""
            friendly_answer = ""
            col_names = []
            rows = []
            direct_success = False

            try:
                # 2. Try the fast, offline direct NLP query interpreter first
                last_intent = request.session.get('last_chatbot_intent')
                last_filters = request.session.get('last_chatbot_filters')
                direct_res = interpret_query_direct(question, mem_conn, last_intent=last_intent, last_filters=last_filters, user=request.user)
                if direct_res.get('success'):
                    sql = direct_res.get('sql', '')
                    col_names = direct_res.get('columns', [])
                    rows = direct_res.get('rows', [])
                    friendly_answer = direct_res.get('answer', '')
                    direct_success = True
                    # Store current intent and filters for subsequent conversational follow-up questions
                    request.session['last_chatbot_intent'] = direct_res.get('intent')
                    request.session['last_chatbot_filters'] = direct_res.get('filters')
                else:
                    # 3. Fallback: Ask Ollama to translate the question to SQL
                    sql = generate_sql_from_question(model, question, request.user)

                    # 4. Securely validate the SQL statement
                    validate_sql_query(sql)

                    # 5. Execute the SQL on the isolated sandbox database
                    col_names, rows = execute_sandboxed_query(mem_conn, sql)

                    # 6. Ask Ollama to format the query result as a human-friendly response
                    friendly_answer = generate_friendly_answer(model, question, sql, col_names, rows)

            except Exception as inner_e:
                error_msg = str(inner_e)
                if not direct_success:
                    error_msg = (
                        f"{str(inner_e)}\n\n"
                        "💡 **Supported Query Examples (processed instantly & offline):**\n"
                        "- *Total counts*: 'How many registered agniveers?', 'How many active trainees in Tirah company?'\n"
                        "- *Averages & rankings*: 'What is the average BPET score?', 'Who is first in Firing in Megiddo company?'\n"
                        "- *Details search*: 'Show details for Agniveer One', 'Find trade DMV agniveers in P2 platoon'\n"
                        "- *Logs & Users*: 'Show recent activity logs', 'List all users'"
                    )
            finally:
                mem_conn.close()

            # Handle failures
            if error_msg:
                log_action(
                    request.user,
                    'CHATBOT',
                    f"Chatbot failed for question '{question[:50]}': {error_msg}",
                    request
                )
                return JsonResponse({
                    'success': False,
                    'error': error_msg,
                    'sql': sql
                }, status=400)

            # Log successful query
            log_action(
                request.user,
                'CHATBOT',
                f"Chatbot query successful for question '{question[:50]}' using {model}",
                request
            )

            # Format data to list of lists for JSON output
            formatted_rows = [list(row) for row in rows]

            return JsonResponse({
                'success': True,
                'sql': sql,
                'columns': col_names,
                'rows': formatted_rows,
                'answer': friendly_answer,
                'direct': direct_success
            })

        except Exception as e:
            return JsonResponse({'success': False, 'error': f"Internal server error: {str(e)}"}, status=500)


class ChatbotModelsApiView(CommanderOrDeptMixin, View):
    """
    Fetches the list of locally running Ollama models.
    """
    def get(self, request):
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode('utf-8'))
                models = [m.get('name') for m in data.get('models', [])]
                return JsonResponse({'success': True, 'models': models})
        except Exception:
            # Safe fallback if Ollama server is briefly unreachable
            return JsonResponse({'success': True, 'models': ['Mistral:latest', 'llama3.2:1b']})




