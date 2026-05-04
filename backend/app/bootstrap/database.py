from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.core.database import engine


BASELINE_REVISION = "20260429_0001"
HEAD_REVISION = "20260504_0003"
LEGACY_BASELINE_TABLES = {
    "artifacts",
    "vendor_assets",
    "generation_jobs",
    "parsed_drawings",
}
CURRENT_HEAD_TABLES = LEGACY_BASELINE_TABLES | {
    "catalog_products",
    "catalog_parameter_specs",
    "catalog_variants",
    "geometry_cache_metrics",
}


def ensure_database_schema_current() -> str:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    has_alembic_version_table = "alembic_version" in table_names
    legacy_tables_present = table_names & LEGACY_BASELINE_TABLES
    legacy_baseline_complete = LEGACY_BASELINE_TABLES.issubset(table_names)
    current_head_complete = CURRENT_HEAD_TABLES.issubset(table_names)
    current_revision = _current_revision() if has_alembic_version_table else None
    has_alembic_revision = current_revision is not None

    config = _alembic_config()
    if not has_alembic_revision and legacy_tables_present and not legacy_baseline_complete:
        raise RuntimeError(
            "Database contains a partial legacy schema without alembic_version. "
            "Back up the database and reconcile it before running automated migrations."
        )

    if current_head_complete and current_revision != HEAD_REVISION:
        command.stamp(config, HEAD_REVISION)
        return "stamped_current_schema"

    if not has_alembic_revision and legacy_baseline_complete:
        command.stamp(config, BASELINE_REVISION)
        command.upgrade(config, "head")
        return "stamped_legacy_and_upgraded"

    command.upgrade(config, "head")
    return "upgraded"


def _alembic_config() -> Config:
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    return config


def _current_revision() -> str | None:
    with engine.connect() as connection:
        row = connection.execute(text("SELECT version_num FROM alembic_version")).first()
    return None if row is None else str(row[0])


if __name__ == "__main__":
    result = ensure_database_schema_current()
    print(f"Database migration result: {result}")
