"""Conservative deterministic Eq gate; uncertain cases go to the logged grader."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation

VERSION = 'eq-conservative-20260905-v2'
ABSTENTIONS = {'unknown', 'n/a', 'cannot determine', 'i do not know', 'i don\'t know', 'insufficient information'}

def normalize(value):
    text = unicodedata.normalize('NFKC', str(value)).strip().casefold()
    text = text.replace('−', '-').replace('’', "'")
    text = re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))', '', text)
    text = re.sub(r'\bus\s*\$', ' USD ', text, flags=re.I)
    # A bare dollar sign is not universally USD (e.g. Canadian/Australian sources).
    text = text.replace('$', ' DOLLAR_SYMBOL ')
    text = text.replace('€', ' EUR ').replace('£', ' GBP ')
    text = text.replace('%', ' percent ')
    return re.sub(r'\s+', ' ', text).strip().casefold()

def fast_match(gold, prediction):
    g, p = normalize(gold), normalize(prediction)
    if not p or p in ABSTENTIONS:
        return False
    if p == g:
        return True
    if re.search(r'\b(?:or|alternatively)\b', p) and not re.search(r'\b(?:or|alternatively)\b', g):
        return False
    # Only parse a single standalone quantity, preserving currency, scale and unit.
    pattern = r'(usd |eur |gbp |dollar_symbol )?([+-]?\d+(?:\.\d+)?)(?: (percent|percentage points|million|billion|trillion|km|kg|miles))?'
    gm, pm = re.fullmatch(pattern, g), re.fullmatch(pattern, p)
    if gm and pm:
        if gm.group(1) != pm.group(1) or gm.group(3) != pm.group(3):
            return None  # Conversion or a missing unit needs contextual grading.
        return Decimal(gm.group(2)) == Decimal(pm.group(2))
    # No punctuation stripping, substring acceptance, or global numeric tolerance.
    return None
