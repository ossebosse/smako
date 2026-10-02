"""Synthetic parser boundary fixtures; factual rows come from retained public sources."""

import hashlib
import json

import pytest

from grocery_data.app.services.product_declarations import parse_declaration

URL = "https://www.gogreen.se/produkter/roda-linser/"


def source(body, url):
    return {"url": url, "resolved_url": url, "status": 200,
            "observed_at": "2026-10-02T16:00:00+00:00", "sha256": hashlib.sha256(body).hexdigest()}


def documents():
    body = ("""<html><meta property="og:site_name" content="GoGreen"><h1>Röda linser</h1>
      <script type="application/ld+json">""" + json.dumps({"@type": "product", "name": "Röda linser"}) + """</script>
      <h2>Ingredienser</h2><div class="content-productcontents"><p>Torkade, skalade och delade röda linser.</p></div>
      <h2>Näringsvärde per 100 g</h2><table><tr><td>Energi</td><td>1460 kJ/349 kcal</td></tr>
      <tr><td>Fett</td><td>1,8 g</td></tr><tr><td>Kolhydrat</td><td>51 g</td></tr>
      <tr><td>Protein</td><td>26 g</td></tr></table></html>""").encode()
    index = b'<a class="callout-link" href="/produkter/roda-linser/"><h3 class="callout-title">R\xc3\xb6da linser</h3><p class="callout-measure">400 g</p></a>'
    return body, index


def parse(body, index):
    return parse_declaration(body, source(body, URL), identity_body=index,
                             identity_acquisition=source(index, "https://www.gogreen.se/produkter/"))


def test_package_needs_unique_linked_official_index_and_gtin_remains_unknown():
    body, index = documents()
    row = parse(body, index)
    assert row["gtin"] is None
    assert row["package_quantity"] == 400
    assert row["culinary_forms"] == ["red_split"]
    assert row["nutrition"]["protein_g"] == 26
    with pytest.raises(ValueError, match="not_unique"):
        parse(body, index + index)
    with pytest.raises(ValueError):
        parse(body, index.replace(b"400 g", b"400 ml"))


@pytest.mark.parametrize("change", [
    {"status": 403}, {"sha256": "changed"}, {"url": "https://example.com/produkter/roda-linser/"},
    {"resolved_url": "https://example.com/redirect"},
])
def test_unverified_or_changed_source_never_becomes_product_facts(change):
    body, index = documents()
    with pytest.raises(ValueError):
        parse_declaration(body, {**source(body, URL), **change}, identity_body=index,
                          identity_acquisition=source(index, "https://www.gogreen.se/produkter/"))


def test_plain_red_colour_does_not_prove_split_or_peeled_form():
    body, index = documents()
    changed = body.replace("Torkade, skalade och delade röda linser.".encode(), "Torkade röda linser.".encode())
    assert parse(changed, index)["culinary_forms"] == []
    with pytest.raises(ValueError):
        parse(body.replace(b"per 100 g", b"per 100 ml"), index)
    with pytest.raises(ValueError):
        parse(body.replace(b"<tr><td>Protein</td><td>26 g</td></tr>", b""), index)
