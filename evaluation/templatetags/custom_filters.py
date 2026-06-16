from django import template

register = template.Library()

@register.filter
def get(dictionary, key):
    """Get a value from a dictionary by key."""
    if isinstance(dictionary, dict):
        return dictionary.get(key, [])
    return []

@register.filter
def get_item(dictionary, key):
    if not dictionary or not hasattr(dictionary, 'get'):
        return None
    return dictionary.get(key)

@register.filter
def get_eval_sheet(evaluations, test_type):
    for ev in evaluations:
        if ev.test_type == test_type:
            return ev
    return None
@register.filter
def get_form_field(form, field_name):
    try:
        return form[field_name]
    except (KeyError, TypeError):
        return None

@register.filter
def department_name(code):
    return {
        'A': 'Battalion',
        'B': 'TTS',
        'C': 'CS',
        'D': 'Clerk',
    }.get(code, code)

@register.filter
def split_str(val, delimiter=','):
    if not val:
        return []
    return val.split(delimiter)

@register.filter
def to_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0

@register.filter
def contains_str(val, search_str):
    if not val:
        return False
    return search_str in str(val)

import re

@register.filter
def has_parenthesized_number(val):
    if not val:
        return False
    return bool(re.search(r'\(\d+\)', str(val)))

@register.filter
def clean_sub_event_name(val):
    if not val:
        return ""
    val_str = str(val)
    if val_str.startswith("BFC CONVERTED"):
        return val_str[4:]
    if val_str.startswith("PDP CONVERTED"):
        return val_str[4:]
    return val_str


import re

@register.filter
def get_sheet_sub_events(sheet):
    if not sheet:
        return []
    
    # Extract marks dict
    res = sheet.sub_event_results or {}
    marks_dict = {}
    if isinstance(res, dict):
        if isinstance(res.get('Marks'), dict):
            marks_dict = res['Marks']
        else:
            # Check if there is an evaluator key like admin/officer/jco/nco
            for ev in ['admin', 'officer', 'jco', 'nco']:
                if isinstance(res.get(ev), dict) and res[ev]:
                    marks_dict = res[ev]
                    break
            if not marks_dict:
                marks_dict = res

    if not isinstance(marks_dict, dict):
        return []

    sub_events = []
    exclude_patterns = ['total', 'percentage', 'result', 'grading', 'status', 'remarks', 'convert', 'grand', 'round']

    for k, v in marks_dict.items():
        k_lower = k.lower()
        if any(p in k_lower for p in exclude_patterns):
            continue
        if k in ['Marks', 'admin', 'nco', 'jco', 'officer']:
            continue
            
        # Parse clean name and max marks
        match = re.search(r'\((MM\s*|Max\s*Marks\s*)?(\d+)[^)]*\)', k)
        if match:
            max_val = int(match.group(2))
            clean_k = re.sub(r'\((MM\s*|Max\s*Marks\s*)?(\d+)[^)]*\)', '', k).strip()
        else:
            max_val = '—'
            clean_k = k.strip()

        # Format scores to 1 decimal place if numeric
        try:
            val_float = float(v)
            val_str = f"{val_float:.1f}"
        except (ValueError, TypeError):
            val_str = str(v) if v is not None else '—'

        sub_events.append({
            'name': clean_k,
            'score': val_str,
            'max': max_val
        })

    return sub_events


@register.filter
def get_universal_dept_name(dept_code, agniveer):
    if not dept_code:
        return ""
    dept_code = str(dept_code).strip().upper()
    trade = str(agniveer.trade or '').strip().upper() if agniveer else ""
    
    if dept_code == 'A':
        bn = str(agniveer.bn_desp or '').strip().lower() if agniveer else ""
        if '1tb' in bn:
            return "1tb"
        elif '2tb' in bn or '2b' in bn:
            return "2tb"
        return "1tb"
    elif dept_code == 'B':
        if trade == 'DMV':
            return "dmv department"
        elif trade == 'OPEM':
            return "opem"
        else:
            return "tts department"
    elif dept_code == 'C':
        return "CES DEpartment"
    elif dept_code == 'D':
        return "cts department"
    return dept_code


@register.filter
def is_total_or_converted(val):
    if not val:
        return False
    val_lower = str(val).lower()
    return 'total' in val_lower or 'converted' in val_lower or 'round' in val_lower


