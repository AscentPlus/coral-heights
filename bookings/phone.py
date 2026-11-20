import re

def canonicalize_phone(phone: str) -> str:
    """
    Canonicalizes an Indian or international phone number.
    - Strips spaces, dashes, parentheses, dots.
    - Removes leading '+91' or '91' for 10-digit Indian numbers.
    - Removes leading '0' for 11-digit numbers starting with 0.
    - Keeps '+' prefix for international numbers.
    """
    if not phone:
        return ""
    cleaned = re.sub(r'[\s\-\(\)\.]+', '', str(phone).strip())
    # If starts with +91 and 10 digits follow
    if cleaned.startswith('+91'):
        candidate = cleaned[3:]
        if len(candidate) == 10 and candidate.isdigit():
            return candidate
    # If starts with 91 and has 12 digits
    if len(cleaned) == 12 and cleaned.startswith('91') and cleaned.isdigit():
        return cleaned[2:]
    # If starts with 0 and has 11 digits
    if len(cleaned) == 11 and cleaned.startswith('0') and cleaned.isdigit():
        return cleaned[1:]
    # Standard 10-digit Indian mobile starting with 6, 7, 8, or 9
    if len(cleaned) == 10 and cleaned.isdigit():
        return cleaned
    return cleaned


def is_valid_phone(phone: str) -> bool:
    """
    Validates canonical phone string.
    Accepts 10-digit Indian mobile (starts with 6-9) or E.164 international.
    """
    if not phone:
        return False
    # 10-digit Indian mobile
    if re.match(r'^[6-9]\d{9}$', phone):
        return True
    # Standard E.164 international phone number (e.g. +14155552671)
    if re.match(r'^\+[1-9]\d{7,14}$', phone):
        return True
    # Generic numeric fallback with 10-14 digits
    if phone.isdigit() and 10 <= len(phone) <= 14:
        return True
    return False

