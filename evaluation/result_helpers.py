ALL_BATTALION_UNITS_LIST = ['1TB', '2TB', '3TB', '4TB', '5TB', 'STB', '1 TB', '2 TB', '3 TB', '4 TB', '5 TB']

def get_bn_desp_list(unit):
    if not unit:
        return []
    if isinstance(unit, (list, tuple, set)):
        res = []
        for u in unit:
            res.extend(get_bn_desp_list(u))
        return list(set(res))
        
    u_str = str(unit).strip()
    clean = u_str.replace(" ", "").upper()
    variations = [u_str, clean]
    if clean.endswith("TB"):
        prefix = clean[:-2]
        variations.append(f"{prefix} TB")
        variations.append(f"{prefix}TB")
    else:
        variations.append(unit)
    variations = list(set(variations))
    # Add lowercase and uppercase variants
    all_vars = []
    for v in variations:
        all_vars.append(v)
        all_vars.append(v.upper())
        all_vars.append(v.lower())
    return list(set(all_vars))

def get_bn_desp_q(field_name, unit):
    from django.db.models import Q
    vars_list = get_bn_desp_list(unit)
    if not vars_list:
        return Q()
    return Q(**{f"{field_name}__in": vars_list})

def get_grade(percentage, subjects=None, passing_pct=46):
    if percentage >= 80:
        tentative_grade = 'Distinction'
    elif percentage >= 70:
        tentative_grade = 'A'
    elif percentage >= 60:
        tentative_grade = 'B'
    elif percentage >= passing_pct:
        tentative_grade = 'C'
    else:
        return '—'

    if not subjects:
        return tentative_grade

    def check_subjects_min(min_pct):
        for score, max_val in subjects:
            if max_val > 0:
                if (score / max_val) * 100 < (min_pct - 1e-9):
                    return False
        return True

    if tentative_grade == 'Distinction':
        if check_subjects_min(75):
            return 'Distinction'
        else:
            tentative_grade = 'A'

    if tentative_grade == 'A':
        if check_subjects_min(60):
            return 'A'
        else:
            tentative_grade = 'B'

    if tentative_grade == 'B':
        if check_subjects_min(50):
            return 'B'
        else:
            tentative_grade = 'C'

    if tentative_grade == 'C':
        if check_subjects_min(35):
            return 'C'
        else:
            return '—'

    return '—'


def _marks_from_sheet(sheet):
    if not sheet:
        return {}
    results = sheet.sub_event_results or {}
    return results.get('Marks') if isinstance(results.get('Marks'), dict) else results


def _num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def get_sheet_total_marks(sheet):
    if not sheet:
        return 0.0
    
    # 1. Check related Marks objects (standard Django model way)
    total = sheet.get_total_marks()
    if total > 0:
        return float(total)
        
    # 2. Check sub_event_results JSON
    res = sheet.sub_event_results or {}
    if not isinstance(res, dict):
        return 0.0
        
    # Check root Total
    if 'Total' in res:
        return _num(res.get('Total'))
    if 'total' in res:
        return _num(res.get('total'))
        
    # Check 'Marks' dict
    if isinstance(res.get('Marks'), dict):
        m_dict = res['Marks']
        if 'Total' in m_dict:
            return _num(m_dict.get('Total'))
        for k, v in m_dict.items():
            if 'total' in k.lower():
                return _num(v)
                
    # Check evaluator keys: 'admin', 'nco', 'jco', 'officer'
    for ev in ['admin', 'nco', 'jco', 'officer']:
        if isinstance(res.get(ev), dict):
            ev_dict = res[ev]
            if 'Total' in ev_dict:
                return _num(ev_dict.get('Total'))
            for k, v in ev_dict.items():
                if 'total' in k.lower():
                    return _num(v)
            # Sum up all numeric values
            ev_total = 0.0
            for k, v in ev_dict.items():
                if k not in ['Total', 'Percentage', 'Result', 'Grading']:
                    try:
                        ev_total += float(v or 0)
                    except (ValueError, TypeError):
                        pass
            if ev_total > 0:
                return ev_total
                
    # Sum flat values in res
    flat_total = 0.0
    for k, v in res.items():
        if k not in ['Total', 'Percentage', 'Result', 'Grading', 'Marks', 'admin', 'nco', 'jco', 'officer']:
            try:
                flat_total += float(v or 0)
            except (ValueError, TypeError):
                pass
    return flat_total


def is_sheet_evaluated(sheet):
    if not sheet:
        return False
    if sheet.is_locked:
        return True
    if sheet.marks.exists():
        return True
    res = sheet.sub_event_results
    if res and isinstance(res, dict):
        if any(k not in ['admin', 'nco', 'jco', 'officer'] for k in res.keys()):
            return True
        for k in ['admin', 'nco', 'jco', 'officer']:
            if isinstance(res.get(k), dict) and res[k]:
                return True
    return False


def get_ces_final_marks(agniveer):
    from evaluation.models import EvaluationSheet
    
    sheets = EvaluationSheet.objects.filter(agniveer=agniveer, department='C')
    if not sheets.exists():
        return 0.0
    row = build_cs_result_row(agniveer, list(sheets))
    return row.get('grand_total', 0.0)


def get_btt_final_marks(agniveer):
    from evaluation.models import EvaluationSheet
    CLERK_TRADES = ['CLK', 'CLERK', 'Clerk', 'CLK_SD', 'CLK_IM']
    
    if agniveer.trade in CLERK_TRADES:
        sheets = EvaluationSheet.objects.filter(agniveer=agniveer, department='D')
        if not sheets.exists():
            return 0.0
        row = build_clerk_result_row(agniveer, list(sheets))
        return row.get('grand_total', 0.0)
    else:
        # TTS departments
        sheets = EvaluationSheet.objects.filter(agniveer=agniveer, department='B')
        if not sheets.exists():
            return 0.0
        row = build_tts_result_row(agniveer, list(sheets))
        return row.get('grand_total', 0.0)


def build_tts_result_row(agniveer, sheets):
    sheet_map = {sheet.test_type: sheet for sheet in sheets}
    trade = agniveer.trade

    mid_term = 0
    mid_term_conv = 0
    online = 0
    online_conv = 0
    job = 0
    job_conv = 0
    practical = 0
    practical_conv = 0

    if trade == 'DMV':
        result_sheet = sheet_map.get('DMV_RESULT')
        marks = _marks_from_sheet(result_sheet)
        online = _num(marks.get('Online Test (100)'))
        practical_sheet = sheet_map.get('DMV_PRACTICAL')
        practical = get_sheet_total_marks(practical_sheet) if practical_sheet else _num(marks.get('Practical Test (50)'))
        driving_sheet = sheet_map.get('DMV_DRIVING')
        job = get_sheet_total_marks(driving_sheet) if driving_sheet else _num(marks.get('Driving Test (50)'))
        total_200 = online + practical + job
        
        # Assessment fallback if final/driving/practical marks are all 0
        if total_200 == 0:
            assessment_sheet = sheet_map.get('DMV_ASSESSMENT')
            if assessment_sheet:
                total_assess = get_sheet_total_marks(assessment_sheet)
                grand_total = round((total_assess / 71) * 40, 2)
                percentage = round((total_assess / 71) * 100, 2)
                total_200 = round((total_assess / 71) * 200, 2)
                grading = get_grade(percentage)
            else:
                grand_total = 0.0
                percentage = 0.0
                grading = '—'
        else:
            grand_total = round(total_200 * 0.2, 2)
            percentage = round((total_200 / 200) * 100, 2)
            subjects = [
                (online, 100),
                (practical, 50),
                (job, 50)
            ]
            grading = get_grade(percentage, subjects)
            
        online_conv = round(online * 0.2, 2)
        job_conv = round(job * 0.25, 2)
        practical_conv = round(practical / 6, 2)

    elif trade == 'OPEM':
        result_sheet = sheet_map.get('OPEM_RESULT')
        marks = _marks_from_sheet(result_sheet)
        online = _num(marks.get('Written Test (100)'))
        practical_sheet = sheet_map.get('OPEM_PRACTICAL')
        practical = get_sheet_total_marks(practical_sheet) if practical_sheet else _num(marks.get('Practical Test (50)'))
        maint_sheet = sheet_map.get('OPEM_MAINTENANCE')
        job = get_sheet_total_marks(maint_sheet) if maint_sheet else _num(marks.get('Maintenance Test (50)'))
        total_200 = online + practical + job
        
        # Assessment fallback if final/maintenance/practical marks are all 0
        if total_200 == 0:
            assessment_sheet = sheet_map.get('OPEM_ASSESSMENT')
            if assessment_sheet:
                total_assess = get_sheet_total_marks(assessment_sheet)
                grand_total = round((total_assess / 71) * 40, 2)
                percentage = round((total_assess / 71) * 100, 2)
                total_200 = round((total_assess / 71) * 200, 2)
                grading = get_grade(percentage)
            else:
                grand_total = 0.0
                percentage = 0.0
                grading = '—'
        else:
            grand_total = round(total_200 * 0.2, 2)
            percentage = round((total_200 / 200) * 100, 2)
            subjects = [
                (online, 100),
                (practical, 50),
                (job, 50)
            ]
            grading = get_grade(percentage, subjects)
            
        online_conv = round(online * 0.2, 2)
        job_conv = round(job * 0.25, 2)
        practical_conv = round(practical / 6, 2)

    else:
        result_sheet = sheet_map.get('OTHER_SCREEN_BOARD')
        if result_sheet:
            marks = _marks_from_sheet(result_sheet)
            mid_term = _num(marks.get('Mid Term Test (50)'))
            mid_term_conv = _num(marks.get('Convert In 10 Mks (Mid Term)')) or round(mid_term / 5.0, 2)
            online = _num(marks.get('Online Test (100)'))
            online_conv = _num(marks.get('Convert In 15 Mks')) or round(online * 0.15, 2)
            job = _num(marks.get('Job (40)'))
            job_conv = _num(marks.get('Convert In 05 Mks')) or round(job / 8.0, 2)
            practical = _num(marks.get('Practical (60)'))
            practical_conv = _num(marks.get('Convert In 10 Mks (Practical)')) or round(practical / 6.0, 2)
            grand_total = _num(marks.get('Grand Total (40)')) or round(mid_term_conv + online_conv + job_conv + practical_conv, 2)
            percentage = _num(marks.get('% Age')) or round(grand_total * 2.5, 2)
            subjects = [
                (mid_term, 50),
                (online, 100),
                (job, 40),
                (practical, 60)
            ]
            grading = marks.get('Grading') or get_grade(percentage, subjects)
        else:
            assessment_sheet = sheet_map.get('OTHER_ASSESSMENT')
            if assessment_sheet:
                total_assess = get_sheet_total_marks(assessment_sheet)
                grand_total = round((total_assess / 70) * 40, 2)
                percentage = round((total_assess / 70) * 100, 2)
                grading = get_grade(percentage)
            else:
                grand_total = 0.0
                percentage = 0.0
                grading = '—'
            online = 0
            job = 0
            practical = 0
            online_conv = 0
            job_conv = 0
            practical_conv = 0

    is_pass = percentage >= 50
    if not is_pass:
        grading = '—'

    return {
        'agniveer': agniveer,
        'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
        'rank': getattr(agniveer, 'rank', '') or '',
        'trade': trade or '',
        'name': agniveer.get_full_name(),
        'unit': agniveer.bn_desp or '',
        'mid_term': mid_term,
        'mid_term_conv': mid_term_conv,
        'online': online,
        'online_conv': online_conv,
        'job': job,
        'job_conv': job_conv,
        'practical': practical,
        'practical_conv': practical_conv,
        'grand_total': grand_total,
        'percentage': percentage,
        'grading': grading,
        'is_pass': is_pass,
        'total_200': total_200 if (trade in ['DMV', 'OPEM']) else 0,
        'max_total': 40,
        'remarks': result_sheet.remarks if (result_sheet and hasattr(result_sheet, 'remarks') and result_sheet.remarks) else '',
    }


def build_cs_result_row(agniveer, sheets):
    from .constants import CS_CLERK_RESULT_TRADES

    sheet_map = {sheet.test_type: sheet for sheet in sheets}
    is_clerk_trade = agniveer.trade in CS_CLERK_RESULT_TRADES
    if is_clerk_trade:
        sheet = sheet_map.get('CS_CLERK_RESULT')
        score_key = 'Total (40)'
    else:
        sheet = sheet_map.get('CS_RESULT')
        score_key = 'CONVERTED TO 40'
        
    if not sheet:
        sheet = sheet_map.get('CS_ASSESSMENT')
        score_key = 'Total (40)'
        
    marks = _marks_from_sheet(sheet)
    total = _num(marks.get(score_key)) or get_sheet_total_marks(sheet)
    percentage = round((total / 40) * 100, 2) if total else 0
    is_pass = percentage >= 50
    grading = get_grade(percentage, passing_pct=50)
    if not is_pass:
        grading = '—'
        
    res_dict = {
        'agniveer': agniveer,
        'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
        'rank': getattr(agniveer, 'rank', '') or '',
        'trade': agniveer.trade or '',
        'name': agniveer.get_full_name(),
        'unit': agniveer.bn_desp or '',
        'grand_total': round(total, 2),
        'percentage': percentage,
        'grading': grading,
        'is_pass': is_pass,
        'max_total': 40,
        'remarks': sheet.remarks if (sheet and hasattr(sheet, 'remarks') and sheet.remarks) else '',
        'is_cs_clerk': is_clerk_trade,
    }

    if is_clerk_trade:
        res_dict['online'] = _num(marks.get('Online (20)'))
        res_dict['prac'] = _num(marks.get('TPrac (20)'))
        res_dict['total_40'] = _num(marks.get('Total (40)')) or (res_dict['online'] + res_dict['prac'])
    else:
        toet_i = _num(marks.get('TOET-I (25)'))
        toet_ii = _num(marks.get('TOET-II (25)'))
        toet_total = _num(marks.get('TOTAL TOET (50)')) or (toet_i + toet_ii)
        toet_25 = _num(marks.get('25% OF TOET (25)')) or round(toet_total * 0.5, 2)
        fe_online = _num(marks.get('FE Online Exam (50)'))
        fe_prac = _num(marks.get('FE Prac (20)'))
        fe_total = _num(marks.get('FE Total (70)')) or (fe_online + fe_prac)
        br_online = _num(marks.get('BR Online Exam (40)'))
        br_prac = _num(marks.get('BR Prac (25)'))
        br_total = _num(marks.get('BR Total (65)')) or (br_online + br_prac)
        total_160 = _num(marks.get('TOTAL (160)')) or (toet_total + fe_total + br_total)
        converted_40 = _num(marks.get('CONVERTED TO 40')) or round(total_160 * 0.25, 2)

        res_dict.update({
            'toet_i': toet_i,
            'toet_ii': toet_ii,
            'toet_total': toet_total,
            'toet_25': toet_25,
            'fe_online': fe_online,
            'fe_prac': fe_prac,
            'fe_total': fe_total,
            'br_online': br_online,
            'br_prac': br_prac,
            'br_total': br_total,
            'total_160': total_160,
            'converted_40': converted_40,
        })
        
    return res_dict


def build_clerk_result_row(agniveer, sheets):
    sheet_map = {sheet.test_type: sheet for sheet in sheets}
    sheet = sheet_map.get('CLK_FINAL') or sheet_map.get('CLK_WEEKLY_2') or sheet_map.get('CLK_WEEKLY_1') or sheet_map.get('CLK_INITIAL')
    marks = _marks_from_sheet(sheet)
    total = 0
    max_total = 40
    subjects = []
    
    # Initialize all sub-event details with default values
    tech_online = 0
    tech_proj = 0
    academic = 0
    comp_online = 0
    comp_prac = 0
    comp_total = 0
    extempore = 0
    typing_20 = '—'
    marks_obtained_300 = 0
    
    if sheet:
        test_type = sheet.test_type
        if test_type == 'CLK_INITIAL':
            academic = _num(marks.get('Academic Written (100)'))
            comp_proj = _num(marks.get('Computer Project Work (25)'))
            total = academic + comp_proj
            max_total = 125
            subjects = [
                (academic, 100),
                (comp_proj, 25)
            ]
        elif test_type == 'CLK_WEEKLY_1':
            tech = _num(marks.get('Tech Written (50)'))
            tech_online = tech
            academic = _num(marks.get('Academic Written (50)'))
            comp_obj = _num(marks.get('Computer Obj (25)'))
            comp_online = comp_obj
            comp_prac = _num(marks.get('Computer Prac (25)'))
            comp_total = _num(marks.get('Computer Total (50)')) or (comp_obj + comp_prac)
            total = tech + academic + comp_obj + comp_prac
            max_total = 150
            subjects = [
                (tech, 50),
                (academic, 50),
                (comp_obj, 25),
                (comp_prac, 25)
            ]
            typing_val = _num(marks.get('Typing 20 WPM'))
            typing_20 = 'PASS' if typing_val >= 70 else 'FAIL'
        elif test_type == 'CLK_WEEKLY_2':
            tech_online = _num(marks.get('Tech Online (115)'))
            tech_proj = _num(marks.get('Tech Proj HRMS (25)'))
            academic = _num(marks.get('Academic Online (85)'))
            comp_online = _num(marks.get('Computer Online (25)'))
            comp_prac = _num(marks.get('Computer Prac (25)'))
            comp_total = _num(marks.get('Computer Total (50)')) or (comp_online + comp_prac)
            total = tech_online + tech_proj + academic + comp_online + comp_prac
            max_total = 275
            subjects = [
                (tech_online, 115),
                (tech_proj, 25),
                (academic, 85),
                (comp_online, 25),
                (comp_prac, 25)
            ]
            typing_val = _num(marks.get('Typing 20 WPM'))
            typing_20 = 'PASS' if typing_val >= 70 else 'FAIL'
        elif test_type == 'CLK_FINAL':
            tech_online = _num(marks.get('Tech Online (115)'))
            tech_proj = _num(marks.get('Tech Proj HRMS (25)'))
            academic = _num(marks.get('Academic Online (85)'))
            comp_online = _num(marks.get('Computer Online (25)'))
            comp_prac = _num(marks.get('Computer Prac (25)'))
            comp_total = _num(marks.get('Computer Total (50)')) or (comp_online + comp_prac)
            extempore = _num(marks.get('Extempore (25)'))
            raw_total = tech_online + tech_proj + academic + comp_online + comp_prac + extempore
            total = (raw_total / 300) * 40
            max_total = 40
            subjects = [
                (tech_online, 115),
                (tech_proj, 25),
                (academic, 85),
                (comp_online, 25),
                (comp_prac, 25),
                (extempore, 25)
            ]
            typing_val = marks.get('Typing 20 WPM', '')
            if isinstance(typing_val, (int, float)):
                typing_20 = 'PASS' if typing_val >= 70 else 'FAIL'
            else:
                typing_20 = str(typing_val).upper() if typing_val else '—'
            marks_obtained_300 = raw_total
    else:
        total = 0
        max_total = 40

    percentage = round((total / max_total) * 100, 2) if max_total else 0
    is_pass = percentage >= 46
    grading = get_grade(percentage, subjects, passing_pct=46)
    if not is_pass:
        grading = '—'
    return {
        'agniveer': agniveer,
        'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
        'rank': getattr(agniveer, 'rank', '') or '',
        'trade': agniveer.trade or '',
        'name': agniveer.get_full_name(),
        'unit': agniveer.bn_desp or '',
        'grand_total': round(total, 2),
        'max_total': max_total,
        'percentage': percentage,
        'grading': grading,
        'is_pass': is_pass,
        'tech_online': tech_online,
        'tech_proj': tech_proj,
        'academic': academic,
        'comp_online': comp_online,
        'comp_prac': comp_prac,
        'comp_total': comp_total,
        'extempore': extempore,
        'typing_20': typing_20,
        'marks_obtained_300': marks_obtained_300,
        'remarks': sheet.remarks if (sheet and hasattr(sheet, 'remarks') and sheet.remarks) else '',
    }


def build_battalion_result_row(agniveer, sheets):
    """Build result row from Final Result sheet."""
    from evaluation.models import EvaluationSheet
    sheet_map = {sheet.test_type: sheet for sheet in sheets}
    sheet = sheet_map.get('FINAL_RESULT')
    marks = _marks_from_sheet(sheet)

    cmk_sheet = sheet_map.get('CMK_SHEET') or EvaluationSheet.objects.filter(agniveer=agniveer, test_type='CMK_SHEET').first()
    if cmk_sheet:
        cmk_marks = _marks_from_sheet(cmk_sheet)
        cmk_20 = _num(cmk_marks.get('CONVERTED (20)'))
    else:
        cmk_20 = _num(marks.get('COMMON MIL KNOWLEDGE (20)'))

    basic_tac_40 = get_ces_final_marks(agniveer)
    trade_prof_40 = get_btt_final_marks(agniveer)

    wpn_sheet = sheet_map.get('WPN_HANDLING') or EvaluationSheet.objects.filter(agniveer=agniveer, test_type='WPN_HANDLING').first()
    if wpn_sheet:
        wpn_marks = _marks_from_sheet(wpn_sheet)
        wpn_handling_20 = _num(wpn_marks.get('CONVERTED (20)'))
    else:
        wpn_handling_20 = _num(marks.get('WPN & EQPT HANDLING (20)'))
    total_120 = round(cmk_20 + basic_tac_40 + trade_prof_40 + wpn_handling_20, 2)
    round_figure_120 = round(cmk_20 + basic_tac_40 + trade_prof_40 + wpn_handling_20)

    percentage = round((round_figure_120 / 120) * 100, 2) if round_figure_120 else 0
    is_pass = percentage >= 40
    grading = get_grade(percentage, passing_pct=40)
    if not is_pass:
        grading = '—'

    return {
        'agniveer': agniveer,
        'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
        'rank': getattr(agniveer, 'rank', '') or '',
        'trade': agniveer.trade or '',
        'name': agniveer.get_full_name(),
        'unit': agniveer.bn_desp or '',
        'cmk_20': cmk_20,
        'basic_tac_40': basic_tac_40,
        'trade_prof_40': trade_prof_40,
        'wpn_handling_20': wpn_handling_20,
        'total_120': total_120,
        'round_figure_120': round_figure_120,
        'grand_total': round_figure_120,
        'max_total': 120,
        'percentage': percentage,
        'grading': grading,
        'is_pass': is_pass,
    }


def build_department_result_row(agniveer, sheets, dept):
    if dept == 'A':
        return build_battalion_result_row(agniveer, sheets)
    if dept == 'B':
        return build_tts_result_row(agniveer, sheets)
    if dept == 'C':
        return build_cs_result_row(agniveer, sheets)
    if dept == 'D':
        return build_clerk_result_row(agniveer, sheets)

    total = round(sum(_num(sheet.get_total_marks()) for sheet in sheets), 2)
    max_total = round(sum(_num(sheet.get_max_marks()) for sheet in sheets), 2)
    percentage = round((total / max_total) * 100, 2) if max_total else 0
    return {
        'agniveer': agniveer,
        'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
        'rank': getattr(agniveer, 'rank', '') or '',
        'trade': agniveer.trade or '',
        'name': agniveer.get_full_name(),
        'unit': agniveer.bn_desp or '',
        'grand_total': total,
        'max_total': max_total,
        'percentage': percentage,
        'grading': get_grade(percentage),
        'is_pass': percentage >= 50,
    }
