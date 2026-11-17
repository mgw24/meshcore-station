"""Pure input validation for Companion flood routing; no repeater ACL management."""
import re
REGION = re.compile(r"^#[A-Za-z0-9][A-Za-z0-9_.-]{0,29}$")

def validate_region(value):
    if not isinstance(value, str) or not REGION.fullmatch(value):
        raise ValueError('Region must start with # and contain 1-30 ASCII letters, numbers, dots, underscores or hyphens')
    return value

def normalize_scope(value):
    if value is None or value in ('', '0', '*'):
        return ''
    return validate_region(value)

def validate_catalog(values):
    if not isinstance(values, list) or len(values) > 32:
        raise ValueError('Provide at most 32 region names')
    found = [validate_region(x) for x in values]
    if len(set(found)) != len(found):
        raise ValueError('Region names must be unique')
    return found

def normalize_channel_scopes(data):
    if not isinstance(data, dict) or len(data) > 8:
        raise ValueError('Invalid channel scope map')
    result = {}
    for index, value in data.items():
        if not isinstance(index, str) or index not in tuple(str(i) for i in range(8)):
            raise ValueError('Channel must be numbered 0-7')
        # absent key = inherit; empty string = explicitly unscoped
        if value is None or value == 'inherit':
            continue
        result[index] = normalize_scope(value)
    return result
