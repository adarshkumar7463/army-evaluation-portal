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
        return 'Fail'

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
            return 'Fail'

    return 'Fail'


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


def build_tts_result_row(agniveer, sheets):
    sheet_map = {sheet.test_type: sheet for sheet in sheets}
    trade = agniveer.trade

    if trade == 'DMV':
        result_sheet = sheet_map.get('DMV_RESULT')
        marks = _marks_from_sheet(result_sheet)
        online = _num(marks.get('Online Test (100)'))
        job = _num(marks.get('Driving Test (50)')) or _num(sheet_map.get('DMV_DRIVING').get_total_marks() if sheet_map.get('DMV_DRIVING') else 0)
        practical = _num(marks.get('Practical Test (50)')) or _num(sheet_map.get('DMV_PRACTICAL').get_total_marks() if sheet_map.get('DMV_PRACTICAL') else 0)
    elif trade == 'OPEM':
        result_sheet = sheet_map.get('OPEM_RESULT')
        marks = _marks_from_sheet(result_sheet)
        online = _num(marks.get('Written Test (100)'))
        job = _num(marks.get('Maintenance Test (50)')) or _num(sheet_map.get('OPEM_MAINTENANCE').get_total_marks() if sheet_map.get('OPEM_MAINTENANCE') else 0)
        practical = _num(marks.get('Practical Test (50)')) or _num(sheet_map.get('OPEM_PRACTICAL').get_total_marks() if sheet_map.get('OPEM_PRACTICAL') else 0)
    else:
        result_sheet = sheet_map.get('OTHER_ASSESSMENT')
        online = _num(result_sheet.get_total_marks() if result_sheet else 0)
        job = 0
        practical = 0

    online_conv = round(online * 0.2, 2)
    job_conv = round(job * 0.25, 2)
    practical_conv = round(practical / 6, 2)
    grand_total = round(online_conv + job_conv + practical_conv, 2)
    percentage = round((grand_total / 40) * 100, 2) if grand_total else 0

    subjects = []
    if trade == 'DMV':
        subjects = [
            (online, 100),
            (practical, 50),
            (job, 50)
        ]
    elif trade == 'OPEM':
        subjects = [
            (online, 100),
            (practical, 50),
            (job, 50)
        ]

    return {
        'agniveer': agniveer,
        'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
        'rank': getattr(agniveer, 'rank', '') or '',
        'trade': trade or '',
        'name': agniveer.get_full_name(),
        'unit': agniveer.bn_desp or '',
        'online': online,
        'online_conv': online_conv,
        'job': job,
        'job_conv': job_conv,
        'practical': practical,
        'practical_conv': practical_conv,
        'grand_total': grand_total,
        'percentage': percentage,
        'grading': get_grade(percentage, subjects),
        'is_pass': percentage >= 50,
    }


def build_cs_result_row(agniveer, sheets):
    from .constants import CS_CLERK_RESULT_TRADES

    sheet_map = {sheet.test_type: sheet for sheet in sheets}
    if agniveer.trade in CS_CLERK_RESULT_TRADES:
        sheet = sheet_map.get('CS_CLERK_RESULT')
        score_key = 'Total (40)'
    else:
        sheet = sheet_map.get('CS_RESULT')
        score_key = 'CONVERTED TO 40'
    marks = _marks_from_sheet(sheet)
    total = _num(marks.get(score_key)) or _num(sheet.get_total_marks() if sheet else 0)
    percentage = round((total / 40) * 100, 2) if total else 0
    return {
        'agniveer': agniveer,
        'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
        'rank': getattr(agniveer, 'rank', '') or '',
        'trade': agniveer.trade or '',
        'name': agniveer.get_full_name(),
        'unit': agniveer.bn_desp or '',
        'grand_total': round(total, 2),
        'percentage': percentage,
        'grading': get_grade(percentage),
        'is_pass': percentage >= 50,
    }


def build_clerk_result_row(agniveer, sheets):
    sheet_map = {sheet.test_type: sheet for sheet in sheets}
    sheet = sheet_map.get('CLK_FINAL') or sheet_map.get('CLK_WEEKLY_2') or sheet_map.get('CLK_WEEKLY_1') or sheet_map.get('CLK_INITIAL')
    marks = _marks_from_sheet(sheet)
    total = 0
    max_total = 40
    subjects = []
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
            academic = _num(marks.get('Academic Written (50)'))
            comp_obj = _num(marks.get('Computer Obj (25)'))
            comp_prac = _num(marks.get('Computer Prac (25)'))
            total = tech + academic + comp_obj + comp_prac
            max_total = 150
            subjects = [
                (tech, 50),
                (academic, 50),
                (comp_obj, 25),
                (comp_prac, 25)
            ]
        elif test_type == 'CLK_WEEKLY_2':
            tech_online = _num(marks.get('Tech Online (115)'))
            tech_proj = _num(marks.get('Tech Proj HRMS (25)'))
            academic = _num(marks.get('Academic Online (85)'))
            comp_online = _num(marks.get('Computer Online (25)'))
            comp_prac = _num(marks.get('Computer Prac (25)'))
            total = tech_online + tech_proj + academic + comp_online + comp_prac
            max_total = 275
            subjects = [
                (tech_online, 115),
                (tech_proj, 25),
                (academic, 85),
                (comp_online, 25),
                (comp_prac, 25)
            ]
        elif test_type == 'CLK_FINAL':
            tech_online = _num(marks.get('Tech Online (115)'))
            tech_proj = _num(marks.get('Tech Proj HRMS (25)'))
            academic = _num(marks.get('Academic Online (85)'))
            comp_online = _num(marks.get('Computer Online (25)'))
            comp_prac = _num(marks.get('Computer Prac (25)'))
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
    else:
        total = 0
        max_total = 40

    percentage = round((total / max_total) * 100, 2) if max_total else 0
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
        'grading': get_grade(percentage, subjects),
        'is_pass': percentage >= 46,
    }


def build_battalion_result_row(agniveer, sheets):
    """Build result row from CMK master sheet (Common Mil Knowledge)."""
    sheet_map = {sheet.test_type: sheet for sheet in sheets}
    sheet = sheet_map.get('CMK_SHEET')
    marks = _marks_from_sheet(sheet)

    fc_prac   = _num(marks.get('FC/BC PRAC (30)'))
    fc_online = _num(marks.get('FC/BC ONLINE TEST (30)'))
    camp_trg  = _num(marks.get('CAMP TRG (30)'))
    mr_conv   = _num(marks.get('CONVERTED TO 40'))
    bfc_conv  = _num(marks.get('BFC CONVERTED TO 15'))
    pdp_conv  = _num(marks.get('PDP CONVERTED TO 15'))
    total_160 = _num(marks.get('TOTAL (160)')) or round(fc_prac + fc_online + camp_trg + mr_conv + bfc_conv + pdp_conv, 2)
    conv_20   = _num(marks.get('CONVERTED TO 20')) or round(total_160 * 20 / 160, 2) if total_160 else 0

    percentage = round((conv_20 / 20) * 100, 2) if conv_20 else 0

    return {
        'agniveer': agniveer,
        'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
        'rank': getattr(agniveer, 'rank', '') or '',
        'trade': agniveer.trade or '',
        'name': agniveer.get_full_name(),
        'unit': agniveer.bn_desp or '',
        'fc_prac': fc_prac,
        'fc_online': fc_online,
        'camp_trg': camp_trg,
        'mr_conv': mr_conv,
        'bfc_conv': bfc_conv,
        'pdp_conv': pdp_conv,
        'total_160': total_160,
        'conv_20': conv_20,
        'grand_total': conv_20,
        'max_total': 20,
        'percentage': percentage,
        'grading': get_grade(percentage, passing_pct=40),
        'is_pass': percentage >= 40,
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
