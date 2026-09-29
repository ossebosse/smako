"""Stable household scope across text-rule versions and physical stores."""
import hashlib
import json
from decimal import Decimal


def household_contract(ad):
    key = [" ".join(ad[k].split()).casefold() for k in ('title', 'brand')]
    key += [str(Decimal(str(ad['package_quantity'])).normalize()) if ad['package_quantity'] is not None else 'unknown', ad['package_unit'],
            ad['valid_from'], ad['valid_to']]
    return 'willys:household:' + hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()[:24]
