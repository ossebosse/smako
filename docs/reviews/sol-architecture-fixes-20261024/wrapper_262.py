# Imports follow the reference pin, exactly as in the measured container.
from pathlib import Path

from app.services import reference_library

reference_library.PIN = Path('/review/backend/app/data/recipes/reference-library-262.json')
from app.services.recipe_library import current_recipes

assert len(current_recipes()) == 262
import runpy

runpy.run_path('/review/docs/reviews/integration-scaling-20261023/run_matrix.py', run_name='__main__')
