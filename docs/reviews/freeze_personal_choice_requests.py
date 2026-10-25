"""Capture the actual personal UI payload, then bind the frozen Malmö stores.

The existing browser fixture returns a deliberate 422 after capture. It never
plans or mocks a price result. Only location's stub IDs/postcode are replaced
with the authorized frozen area's exact IDs before real API measurements.
"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from backend.tests.test_personal_choices_browser import choices, choose_location, done, edit, submit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    old = json.loads(args.base.read_text(encoding='utf8'))['requests']['A']
    fixture = choices.__wrapped__(SimpleNamespace(param='chromium'))
    page, url, captured = next(fixture)
    result = {}
    page.goto(url)
    choose_location(page)
    edit(page, 'dinner-count', 5)
    edit(page, 'dinner-servings', 4)

    def capture(case):
        body = submit(page, captured)
        body['postal_code'] = old['postal_code']
        body['allowed_store_ids'] = old['allowed_store_ids']
        result[case] = body

    capture('A')
    page.locator('#extra-choices>summary').click()
    page.locator('#cuisine-italian').check()
    page.locator('#cuisine-indian').check()
    capture('B')
    page.locator('#cuisine-italian').uncheck()
    page.locator('#cuisine-indian').uncheck()
    page.locator('#dinner-nutrition-open').click()
    edit(page, 'dinner-min_protein_g', 40)
    done(page, 'dinner', 'nutrition')
    capture('C')
    page.locator('#dinner-nutrition-open').click()
    page.locator('#dinner-min_protein_g-value').fill('')
    done(page, 'dinner', 'nutrition')
    page.locator('#dinner-distribution-open').click()
    for kind, count in (('chicken', 3), ('vegetarian', 2), ('meat', 0), ('fish', 0)):
        edit(page, 'dinner-' + kind, count)
    done(page, 'dinner', 'distribution')
    capture('D')
    page.locator('#cuisine-italian').check()
    page.locator('#cuisine-indian').check()
    page.locator('#dinner-nutrition-open').click()
    edit(page, 'dinner-min_protein_g', 40)
    done(page, 'dinner', 'nutrition')
    capture('E')
    try:
        next(fixture)
    except StopIteration:
        pass
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
