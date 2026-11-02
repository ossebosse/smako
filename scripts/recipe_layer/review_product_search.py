"""Broaden manual review suggestions; never grant identity or price approval."""
from app.services.ingredient_normalizer import _search_text


def review_search_key(text):
    """Ignore spacing in labels such as 'Lime Blad Torkade'."""
    return _search_text(text).replace(' ', '')


def review_search_matches(label_key, query_keys):
    return any(query and query in label_key for query in query_keys)
