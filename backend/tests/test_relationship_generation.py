from app.services.spec_parser import build_blueprint


# Integration guard: clear 1..* spec should produce relationship output.
def test_relationships_generated_for_simple_parent_child_spec():
    spec = "A school has many students. Each student belongs to one school."
    result = build_blueprint(spec)

    relationships = result.get("relationships", [])
    assert isinstance(relationships, list)
    assert len(relationships) > 0
