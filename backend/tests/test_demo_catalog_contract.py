from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_demo_catalog_exposes_five_products():
    response = client.get("/api/v1/products")

    assert response.status_code == 200
    products = response.json()
    product_ids = {product["product_id"] for product in products}
    assert {
        "hex-bolt-iso4014",
        "hex-nut-iso4032",
        "washer-iso7089",
        "retaining-ring-gb891",
        "hex-bolt-din931",
        "washer-din125",
    }.issubset(product_ids)


def test_local_frontend_origin_is_allowed_by_cors():
    response = client.options(
        "/api/v1/products/hex-bolt-iso4014/variants",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_hex_nut_variants_endpoint_exposes_iso4032_dimensions():
    response = client.get("/api/v1/products/hex-nut-iso4032/variants")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 6
    assert "M8" in data["grouped_by_diameter"]
    m8 = data["grouped_by_diameter"]["M8"][0]
    assert m8["params"]["d"] == 8
    assert m8["params"]["s"] == 13.0
    assert m8["params"]["m"] == 6.8
