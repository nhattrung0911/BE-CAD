from app.services.hash_service import stable_params_hash


def test_stable_params_hash_order_independent():
    a = stable_params_hash("p", "v1", "preview", "glb", {"d": 6, "L": 30})
    b = stable_params_hash("p", "v1", "preview", "glb", {"L": 30, "d": 6})
    assert a == b
