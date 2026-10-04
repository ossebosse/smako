"""Actual registered recipe content rendered in Chromium/WebKit; no price qualification claim."""
import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT)]
from app.models.recipe_preferences import RecipePreferences
from app.services.recipe_library import candidates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    recipes = [r.model_dump(mode='json') for r in candidates(RecipePreferences(mode='complete'), 4)]
    reports = []
    with sync_playwright() as pw:
        for engine in ('chromium', 'webkit'):
            browser = getattr(pw, engine).launch()
            for width in (390, 1280):
                page = browser.new_page(viewport={'width': width, 'height': 900})
                page.set_content('<html lang="sv"><head><meta charset="utf-8"></head><body><main class="recipe-card"><div class="recipe-content" id="recipe"></div></main></body></html>')
                for name in ('styles.css', 'complete-recipes.css'):
                    path = ROOT / 'backend/app/static' / name
                    if path.exists():
                        page.add_style_tag(path=str(path))
                page.add_style_tag(content='body {margin:16px} main {max-width:1100px;margin:auto} #recipe {display:block;padding:16px}')
                page.add_script_tag(path=str(ROOT / 'backend/app/static/complete-recipes.js'))
                result = page.evaluate('''recipes => {
                  const values={protein_g:31.588999999999995};
                  for (const recipe of recipes) {
                    const before=JSON.stringify(recipe);
                    const view=SmakoRecipes.cookingPresentation(recipe);
                    if(!view.waterOnly)throw new Error('Known method not projected: '+recipe.design.base_id);
                    if(JSON.stringify(recipe)!==before)throw new Error('Saved source mutated');
                    const unknown=structuredClone(recipe);unknown.preparation.version='future-method';
                    if(JSON.stringify(SmakoRecipes.cookingPresentation(unknown).instructions)!==JSON.stringify(unknown.instructions))throw new Error('Unknown method changed');
                    const custom=structuredClone(recipe);custom.instructions[0]+=' Behåll säkerhetsinstruktionen.';
                    if(SmakoRecipes.cookingPresentation(custom).waterOnly)throw new Error('Changed recipe projected');
                  }
                  const recipe=recipes.find(r=>r.design.base_id==='smako-indian-palak-tofu'&&r.design.variant_id==='base');
                  document.querySelector('#recipe').replaceChildren(SmakoRecipes.renderRecipe(recipe,{nutrition:{status:'ESTIMATED',values}}));
                  const title=document.createElement('h1');title.textContent=recipe.name;document.querySelector('#recipe').prepend(title);
                  if(SmakoRecipes.mealDescription(recipe,'vegetarian').includes('Vegetariska'))throw new Error('Plural category');
                  return {count:recipes.length,protein:SmakoRecipes.nutritionNumber(values.protein_g,'ESTIMATED'),raw:values.protein_g};
                }''', recipes)
                card = page.locator('#recipe')
                expect(card).to_contain_text('ca 31,6 g protein')
                expect(card).to_contain_text('Om näringsberäkningen')
                expect(card.locator('.complete-recipe-method')).not_to_contain_text('Endast dricksvatten')
                expect(card.locator('.complete-recipe-method')).not_to_contain_text('provlagning')
                expect(card).not_to_contain_text('31.588999999999995')
                expect(card).to_contain_text('steg 2 och 3 parallellt')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                card.screenshot(path=str(args.output / f'{engine}-{width}-recipe.png'))
                reports.append({'engine': engine, 'width': width, **result, 'physical_device': False})
                page.close()
            browser.close()
    (args.output / 'results.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')
    print(json.dumps(reports))


if __name__ == '__main__':
    main()
