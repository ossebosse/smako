"""Closed projection of public links; never persist retailer runtime/session HTML."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def store_offer_url(links: list[str], store_id: str) -> str | None:
    """Resolve equivalent detail links to one observed, exact store page."""
    matches = set()
    for url in links:
        parsed = urlsplit(url)
        if (parsed.scheme == 'https' and parsed.netloc == 'www.ica.se'
                and re.fullmatch(r'/erbjudanden/[^/]+-' + re.escape(store_id) + r'/?', parsed.path)):
            matches.add('https://www.ica.se' + parsed.path.rstrip('/') + '/')
    return next(iter(matches)) if len(matches) == 1 else None


def public_links(payload: bytes, base_url: str = "https://www.ica.se") -> dict:
    soup = BeautifulSoup(payload, "html.parser")
    flyers, next_pages, offers = set(), set(), set()
    for link in soup.find_all("a", href=True):
        url = urljoin(base_url, link["href"])
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            continue
        label = link.get_text(" ", strip=True).casefold()
        if (parsed.hostname in {"www.e-magin.se", "www.ica.se", "www.ereklamblad.se"}
                and (re.search(r"reklamblad|veckans blad", label)
                     or parsed.hostname == "www.e-magin.se")):
            flyers.add(url)
        if ("next" in link.get("rel", []) and parsed.hostname == "www.ica.se"
                and parsed.path.startswith("/butiker/")):
            next_pages.add(url)
        if parsed.hostname == "www.ica.se" and parsed.path.startswith("/erbjudanden/"):
            offers.add(url)
    return {"flyer_links": sorted(flyers), "next_pages": sorted(next_pages),
            "offers_links": sorted(offers)}
