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
    if not dictionary: return None
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

