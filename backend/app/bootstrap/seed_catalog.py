from app.bootstrap.database import ensure_database_schema_current
from app.core.database import SessionLocal
from app.repositories.catalog import CatalogRepository
from app.services.demo_catalog import CATALOG, VARIANTS


def seed_demo_catalog() -> int:
    ensure_database_schema_current()
    with SessionLocal() as session:
        repository = CatalogRepository(session)
        for product_id, product in CATALOG.items():
            repository.replace_product_catalog(
                product=product,
                variants=VARIANTS.get(product_id, []),
            )
        session.commit()
        return len(CATALOG)


if __name__ == "__main__":
    seeded = seed_demo_catalog()
    print(f"Seeded {seeded} catalog products.")
