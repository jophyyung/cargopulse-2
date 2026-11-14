"""Export canonical OpenAPI and JSON Schemas without a running database."""

import argparse
import json
from pathlib import Path

from cargopulse_contracts import ScenarioSnapshot, SolutionPlan

from packages.contracts.routes import contract_app

parser = argparse.ArgumentParser()
parser.add_argument(
    "--runtime",
    action="store_true",
    help="Export the actual API, including additive runtime routes",
)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
target = root / "packages/contracts"
if args.runtime:
    from cargopulse_api.main import app

    api = app.openapi()
else:
    api = contract_app().openapi()
(target / "openapi.json").write_text(json.dumps(api, indent=2) + "\n")
for model in (ScenarioSnapshot, SolutionPlan):
    (target / f"{model.__name__}.schema.json").write_text(
        json.dumps(model.model_json_schema(mode="serialization"), indent=2) + "\n"
    )
