"""Valide une réponse Flask contre docs/openapi.yaml (PyYAML + jsonschema, dépendances de test seulement)."""
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SPEC = yaml.safe_load((Path(__file__).parents[1] / "docs" / "openapi.yaml").read_text(encoding="utf-8"))
_REGISTRY = Registry().with_resource("urn:openapi", Resource.from_contents(SPEC, default_specification=DRAFT202012))


def _pointer(*parts: str) -> str:
    return "urn:openapi#/" + "/".join(p.replace("~", "~0").replace("/", "~1") for p in parts)


def assert_conforms(resp, path: str, method: str = "get") -> None:
    """Le statut est prévu par le contrat et le corps JSON respecte son schéma."""
    responses = SPEC["paths"][path][method]["responses"]
    status = str(resp.status_code)
    key = status if status in responses else "default"
    assert key in responses, f"{method.upper()} {path} : statut {status} absent du contrat"
    declared = responses[key]
    parts = ["paths", path, method, "responses", key]
    if "$ref" in declared:
        name = declared["$ref"].rsplit("/", 1)[-1]
        declared, parts = SPEC["components"]["responses"][name], ["components", "responses", name]
    if "content" not in declared:
        assert resp.data == b"", f"{status} sans corps attendu"
        return
    if "application/json" not in declared["content"]:
        return  # audio : vérifié par les tests de la voix
    assert resp.mimetype == "application/json", f"type {resp.mimetype} au lieu de JSON"
    schema = {"$ref": _pointer(*parts, "content", "application/json", "schema")}
    Draft202012Validator(schema, registry=_REGISTRY).validate(resp.get_json())
