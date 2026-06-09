def get_grade(percentage):
    if percentage >= 70:
        return 'A'
    if percentage >= 60:
        return 'B'
    return 'C'


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
        'grading': get_grade(percentage),
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
    total = (
        _num(marks.get('Marks Obtained (120.00)')) or
        _num(marks.get('Marks Obtained (126.50)')) or
        _num(marks.get('Marks Obtained (69)')) or
        _num(marks.get('Marks Obtained (50)')) or
        _num(sheet.get_total_marks() if sheet else 0)
    )
    max_total = _num(sheet.get_max_marks() if sheet else 0) or 40
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
        'grading': get_grade(percentage),
        'is_pass': percentage >= 50,
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
        'grading': get_grade(percentage),
        'is_pass': percentage >= 50,
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
