"""Issue explicit measured leaf-only mint versions through the existing importer."""
import argparse

from amend_egg_recipes import issue_reviewed_preparation
from app.services.ingredient_preparations import (
    MINT_LEAF_KEY,
    MINT_LEAVES,
    MINT_OPERAND,
    mint_reference,
)
from app.services.meal_library_content import ROOT


def eligible_names(recipe):
    return {i.canonical_name for i in recipe.ingredients if i.canonical_name == 'mynta'
            and 'pack:' + MINT_LEAF_KEY in i.product_requirements}


def main(do_import):
    issue_reviewed_preparation(do_import,
        output=ROOT / 'reviewed-mint-leaves-20261028',
        report=ROOT.parents[3] / 'docs/reviews/mint-leaf-preparation-20261028',
        method=MINT_LEAVES, operand=MINT_OPERAND, source=mint_reference(), eligible_names=eligible_names,
        pack_id='mint-leaf-trimming-review-20261028',
        instruction='Skölj myntan och rensa bort grova och skadade delar. Väg den ätbara råinsatsen med blad och mjuka delar. Plocka sedan bort alla stjälkar och väg enbart bladen till receptets angivna gram. Inköpets bladutbyte bygger på ett begränsat studieexempel och en separat uppskattning av grovrensning, inte en förpackningsgaranti. Bokför uppmätt råinsats och blad; komplettera vid för litet faktiskt bladutbyte. Stjälkarna ingår inte i receptmängden. Följ förpackningens hantering; ingen hållbarhet är fastställd här. De tre extra aktiva minuterna är en författaruppskattning.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import', dest='do_import', action='store_true')
    main(parser.parse_args().do_import)
