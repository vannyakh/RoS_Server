from tools.compatibility_checker import audit, load_matrix


def test_matrix_makes_no_unproven_compatibility_claim():
    features = load_matrix()
    assert audit(features) == []
    assert features
    assert all(feature["compatibility_status"] == "unknown" for feature in features)
    assert all(feature["original_reference"].startswith("No authorized") for feature in features)
