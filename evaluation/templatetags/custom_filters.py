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

