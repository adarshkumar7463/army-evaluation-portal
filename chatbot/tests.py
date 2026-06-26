from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import CustomUser
from departments.models import Agniveer
from evaluation.models import EvaluationSheet, Marks
from chatbot.services import validate_sql_query, get_filtered_querysets, get_sandboxed_db, interpret_query_direct
import datetime

User = get_user_model()


class ChatbotSecurityTestCase(TestCase):
    """
    Tests checking SQL parsing, validation and sandboxing features.
    """

    def setUp(self):
        # Create users with different roles and subdepartments
        self.commander = User.objects.create_user(
            username='cmd_user',
            password='testpassword123',
            role='commander'
        )
        self.dept_a_1tb = User.objects.create_user(
            username='dept_a_1tb_user',
            password='testpassword123',
            role='dept_a',
            department='A',
            battalion_unit='1TB'
        )
        self.dept_a_2tb = User.objects.create_user(
            username='dept_a_2tb_user',
            password='testpassword123',
            role='dept_a',
            department='A',
            battalion_unit='2TB'
        )
        self.dept_b_dmv = User.objects.create_user(
            username='dept_b_dmv_user',
            password='testpassword123',
            role='dept_b',
            department='B',
            tts_trade='DMV'
        )
        self.dept_b_opem = User.objects.create_user(
            username='dept_b_opem_user',
            password='testpassword123',
            role='dept_b',
            department='B',
            tts_trade='OPEM'
        )

        # Create Agniveers in different units/trades
        self.agn_1tb = Agniveer.objects.create(
            name="Agniveer One",
            agniveer_no="AGN/1001",
            trade="CLK",
            bn_desp="1TB",
            status="active"
        )
        self.agn_2tb = Agniveer.objects.create(
            name="Agniveer Two",
            agniveer_no="AGN/1002",
            trade="DMV",
            bn_desp="2TB",
            status="active"
        )
        self.agn_dmv = Agniveer.objects.create(
            name="Agniveer Three",
            agniveer_no="AGN/1003",
            trade="DMV",
            bn_desp="2TB",
            status="active"
        )
        self.agn_opem = Agniveer.objects.create(
            name="Agniveer Four",
            agniveer_no="AGN/1004",
            trade="OPEM",
            bn_desp="STB",
            status="active"
        )

        # Create evaluations
        self.sheet_1 = EvaluationSheet.objects.create(
            agniveer=self.agn_1tb,
            category='physical',
            test_type='PPT',
            department='A',
            evaluation_date=datetime.date.today()
        )
        self.sheet_2 = EvaluationSheet.objects.create(
            agniveer=self.agn_2tb,
            category='weapon',
            test_type='Firing',
            department='A',
            evaluation_date=datetime.date.today()
        )
        self.sheet_3 = EvaluationSheet.objects.create(
            agniveer=self.agn_dmv,
            category='driving',
            test_type='DMV_ASSESSMENT',
            department='B',
            evaluation_date=datetime.date.today()
        )
        self.sheet_4 = EvaluationSheet.objects.create(
            agniveer=self.agn_opem,
            category='maintenance',
            test_type='OPEM_ASSESSMENT',
            department='B',
            evaluation_date=datetime.date.today()
        )

    def test_sql_validation_allows_safe_selects(self):
        # Normal SELECT
        validate_sql_query("SELECT * FROM departments_agniveer")
        validate_sql_query("SELECT COUNT(*), bn_desp FROM departments_agniveer GROUP BY bn_desp")
        validate_sql_query("SELECT a.name, s.test_type FROM departments_agniveer a JOIN evaluation_evaluationsheet s ON a.id = s.agniveer_id")

    def test_sql_validation_blocks_writes(self):
        # DML statements
        with self.assertRaises(ValueError):
            validate_sql_query("INSERT INTO departments_agniveer (name) VALUES ('Test')")
        with self.assertRaises(ValueError):
            validate_sql_query("UPDATE departments_agniveer SET name = 'Test' WHERE id = 1")
        with self.assertRaises(ValueError):
            validate_sql_query("DELETE FROM departments_agniveer WHERE id = 1")
            
        # DDL statements
        with self.assertRaises(ValueError):
            validate_sql_query("DROP TABLE departments_agniveer")
        with self.assertRaises(ValueError):
            validate_sql_query("ALTER TABLE departments_agniveer ADD COLUMN test INTEGER")

    def test_sql_validation_blocks_injections_and_multiple_stmts(self):
        # Semicolon multi-statement query
        with self.assertRaises(ValueError):
            validate_sql_query("SELECT * FROM departments_agniveer; DROP TABLE evaluation_evaluationsheet")
            
        # Dangerous words checks
        with self.assertRaises(ValueError):
            validate_sql_query("SELECT * FROM departments_agniveer WHERE name = 'test' UNION SELECT password FROM accounts_customuser")

    def test_sandboxing_scoping_commander(self):
        # Commander sees all 4 Agniveers and all 4 sheets
        agns, sheets, marks = get_filtered_querysets(self.commander)
        self.assertEqual(agns.count(), 4)
        self.assertEqual(sheets.count(), 4)

    def test_sandboxing_scoping_dept_a_1tb(self):
        # Dept A (1TB) should only see agn_1tb and sheet_1
        agns, sheets, marks = get_filtered_querysets(self.dept_a_1tb)
        self.assertEqual(agns.count(), 1)
        self.assertEqual(agns.first(), self.agn_1tb)
        self.assertEqual(sheets.count(), 1)
        self.assertEqual(sheets.first(), self.sheet_1)

    def test_sandboxing_scoping_dept_b_dmv(self):
        # Dept B (DMV) should only see trainees in DMV trade (agn_2tb, agn_dmv) and sheet_3 (DMV assessment)
        agns, sheets, marks = get_filtered_querysets(self.dept_b_dmv)
        # DMV trade agniveers
        self.assertEqual(set(agns), {self.agn_2tb, self.agn_dmv})
        # DMV sheets
        self.assertEqual(sheets.count(), 1)
        self.assertEqual(sheets.first(), self.sheet_3)


class ChatbotDirectInterpreterTestCase(TestCase):
    """
    Tests checking direct NLP parsing, entity extraction, and query interpretation.
    """
    def setUp(self):
        # Create users
        self.commander = User.objects.create_user(
            username='cmd_user_direct',
            password='testpassword123',
            role='commander'
        )
        self.dept_a_1tb = User.objects.create_user(
            username='dept_a_1tb_user_direct',
            password='testpassword123',
            role='dept_a',
            department='A',
            battalion_unit='1TB'
        )
        # Create Agniveer records
        self.agn1 = Agniveer.objects.create(
            name="Agniveer One",
            agniveer_no="AGN/1001",
            trade="CLK",
            bn_desp="1TB",
            status="active",
            company="Megiddo Company"
        )
        self.agn2 = Agniveer.objects.create(
            name="Agniveer Two",
            agniveer_no="AGN/1002",
            trade="DMV",
            bn_desp="2TB",
            status="fail",
            company="Tirah Company"
        )
        # Create sheet and marks
        self.sheet = EvaluationSheet.objects.create(
            agniveer=self.agn1,
            category='physical',
            test_type='PPT',
            department='A',
            evaluation_date=datetime.date.today()
        )
        self.mark = Marks.objects.create(
            evaluation_sheet=self.sheet,
            evaluator=self.commander,
            evaluator_type='admin',
            marks=85
        )

    def test_direct_query_total_count(self):
        mem_conn = get_sandboxed_db(self.commander)
        try:
            res = interpret_query_direct("How many active agniveers are registered?", mem_conn)
            self.assertTrue(res['success'])
            self.assertIn("1", res['answer'])
        finally:
            mem_conn.close()

    def test_direct_query_scoping_dept_a(self):
        mem_conn = get_sandboxed_db(self.dept_a_1tb)
        try:
            res = interpret_query_direct("How many registered agniveers?", mem_conn)
            self.assertTrue(res['success'])
            self.assertIn("1", res['answer'])
            
            res_avg = interpret_query_direct("What is the average PPT score?", mem_conn)
            self.assertTrue(res_avg['success'])
            self.assertIn("85", res_avg['answer'])
        finally:
            mem_conn.close()

    def test_direct_query_highest_score(self):
        mem_conn = get_sandboxed_db(self.commander)
        try:
            res = interpret_query_direct("Who got the highest score in PPT?", mem_conn)
            self.assertTrue(res['success'])
            self.assertIn("Agniveer One", res['answer'])
            self.assertIn("85", res['answer'])
        finally:
            mem_conn.close()

    def test_direct_query_pass_fail(self):
        mem_conn = get_sandboxed_db(self.commander)
        try:
            # Query for passed trainees in PPT (should find Agniveer One as 85 >= 40)
            res = interpret_query_direct("list the agniveer pass in PPT evaluation", mem_conn)
            self.assertTrue(res['success'])
            self.assertTrue(any("Agniveer One" in row for row in res['rows']))
            
            # Query for failed trainees in PPT (should find 0)
            res_fail = interpret_query_direct("how many agniveers failed in PPT?", mem_conn)
            self.assertTrue(res_fail['success'])
            self.assertIn("0", res_fail['answer'])
        finally:
            mem_conn.close()

    def test_direct_query_overall_pass_fail(self):
        mem_conn = get_sandboxed_db(self.commander)
        try:
            # Query for passed trainees overall (should find 0)
            res = interpret_query_direct("list the total passed agniveer", mem_conn, user=self.commander)
            self.assertTrue(res['success'])
            self.assertEqual(res['rows'][0][0], 0)
            
            # Query for failed trainees overall (should find 1: Agniveer One)
            res_fail = interpret_query_direct("how many agniveers are fail?", mem_conn, user=self.commander)
            self.assertTrue(res_fail['success'])
            self.assertIn("1", res_fail['answer'])
        finally:
            mem_conn.close()

    def test_direct_query_conversational_followup(self):
        mem_conn = get_sandboxed_db(self.commander)
        try:
            # First turn sets count intent
            res = interpret_query_direct("how many agniveers evaluated in PPT?", mem_conn)
            self.assertTrue(res['success'])
            self.assertIn("1", res['answer'])
            
            # Second turn follow up should inherit 'count' intent
            res_follow = interpret_query_direct("and in firing test?", mem_conn, last_intent='count')
            self.assertTrue(res_follow['success'])
            self.assertIn("0", res_follow['answer'])  # should find 0 firing tests since we only created PPT
        finally:
            mem_conn.close()

    def test_direct_query_pass_percentage(self):
        mem_conn = get_sandboxed_db(self.commander)
        try:
            res = interpret_query_direct("what is the pass percentage in PPT?", mem_conn, user=self.commander)
            self.assertTrue(res['success'])
            self.assertIn("100.0%", res['answer'])
            self.assertEqual(res['rows'][0][0], 100.0)
        finally:
            mem_conn.close()

    def test_direct_query_average_difference(self):
        Agniveer.objects.create(
            name="Agniveer Three",
            agniveer_no="AGN/1003",
            trade="CLK",
            bn_desp="1TB",
            status="active",
            company="Tirah Company"
        )
        sheet3 = EvaluationSheet.objects.create(
            agniveer=Agniveer.objects.get(name="Agniveer Three"),
            category='physical',
            test_type='PPT',
            department='A',
            evaluation_date=datetime.date.today()
        )
        Marks.objects.create(
            evaluation_sheet=sheet3,
            evaluator=self.commander,
            evaluator_type='admin',
            marks=65
        )
        mem_conn = get_sandboxed_db(self.commander)
        try:
            res = interpret_query_direct("difference in average PPT marks between Megiddo company and Tirah company", mem_conn)
            self.assertTrue(res['success'])
            self.assertIn("20", res['answer'])
            self.assertEqual(res['rows'][0][0], 20.0)
        finally:
            mem_conn.close()

    def test_direct_query_rankings_overall(self):
        mem_conn = get_sandboxed_db(self.commander)
        try:
            res = interpret_query_direct("who is the overall top ranker?", mem_conn, user=self.commander)
            self.assertTrue(res['success'])
            self.assertIn("Agniveer One", res['answer'])
            self.assertTrue(any("Agniveer One" in row for row in res['rows']))
        finally:
            mem_conn.close()

    def test_direct_query_report_card(self):
        mem_conn = get_sandboxed_db(self.commander)
        try:
            res = interpret_query_direct("show report card of Agniveer One", mem_conn, user=self.commander)
            self.assertTrue(res['success'])
            self.assertIn("Report Card for Agniveer One", res['answer'])
            self.assertTrue(any("PPT" in row for row in res['rows']))
        finally:
            mem_conn.close()

    def test_direct_query_negations(self):
        mem_conn = get_sandboxed_db(self.commander)
        try:
            res = interpret_query_direct("list trainees but not DMV trade", mem_conn, user=self.commander)
            self.assertTrue(res['success'])
            names = [row[0] for row in res['rows']]
            self.assertIn("Agniveer One", names)
            self.assertNotIn("Agniveer Two", names)
        finally:
            mem_conn.close()

    def test_direct_query_battalion_120_max_marks(self):
        # Set up a sheet and marks for Agniveer One representing overall final test
        EvaluationSheet.objects.create(
            agniveer=self.agn1,
            category='compiled',
            test_type='FINAL_RESULT',
            department='A',
            evaluation_date=datetime.date.today()
        )
        mem_conn = get_sandboxed_db(self.commander)
        try:
            res = interpret_query_direct("who is the overall top ranker?", mem_conn, user=self.commander)
            self.assertTrue(res['success'])
            grand_totals = [row[7] for row in res['rows'] if row[0] == "Agniveer One"]
            if grand_totals:
                self.assertTrue(any("/120" in gt for gt in grand_totals))
        finally:
            mem_conn.close()

    def test_direct_query_cmk_after_bpet(self):
        mem_conn = get_sandboxed_db(self.commander)
        try:
            # Simulate a previous query for BPET
            last_filters = {'test_types': ['BPET']}
            last_intent = 'list'
            
            # Now search for CMK (should NOT fall back to BPET)
            res = interpret_query_direct("top ranker in CMK", mem_conn, last_intent=last_intent, last_filters=last_filters, user=self.commander)
            self.assertTrue(res['success'])
            # Since there are no CMK sheets in DB, it should either be empty or show no evaluated records,
            # but it should NOT contain BPET or PPT test type in the filter.
            self.assertEqual(res['filters']['test_types'], ['CMK_SHEET'])
        finally:
            mem_conn.close()

    def test_direct_query_agniveers_stopword(self):
        mem_conn = get_sandboxed_db(self.commander)
        try:
            res = interpret_query_direct("how many total agniveers are registered", mem_conn, user=self.commander)
            self.assertTrue(res['success'])
            # The filters should not have matched 'Agniveer One' or 'Agniveer Two' name
            self.assertEqual(res['filters']['names'], [])
            # Count query SQL should query the count of all agniveers
            self.assertEqual(res['sql'], "SELECT COUNT(*) FROM departments_agniveer a;")
        finally:
            mem_conn.close()



