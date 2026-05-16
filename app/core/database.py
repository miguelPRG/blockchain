"""Configuração de banco de dados SQLAlchemy e dependência de sessão."""

from collections.abc import Generator
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.settings import settings


class Base(DeclarativeBase):
    """Classe base para modelos ORM SQLAlchemy."""


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """Dependência FastAPI que fornece uma sessão DB com escopo de transação."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sqlite_table_columns(conn, table_name: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").mappings()
    return {row["name"] for row in rows}


def _sqlite_column_types(conn, table_name: str) -> dict[str, str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").mappings()
    return {row["name"]: row["type"].upper() for row in rows}


def _sqlite_table_exists(conn, table_name: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).first()
    return row is not None


def _drop_legacy_indexes(conn, table_name: str) -> None:
    rows = list(conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL",
        (table_name,),
    ))
    for row in rows:
        conn.exec_driver_sql(f'DROP INDEX IF EXISTS "{row[0]}"')


def _drop_migration_leftovers(conn) -> None:
    """Limpar sobras de uma migração SQLite interrompida."""
    for table in ("manifests_legacy_payload_migration", "records_legacy_payload_migration"):
        _drop_legacy_indexes(conn, table)
        conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{table}"')


def _parse_sqlite_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _sqlite_timestamp_value(value) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _migrate_sqlite_payload_storage() -> None:
    """Migrar tabelas antigas para guardar apenas campos do payload off-chain."""
    if engine.dialect.name != "sqlite":
        return

    from app.models.manifest import Manifest
    from app.models.record import Record

    with engine.begin() as conn:
        if _sqlite_table_exists(conn, "manifests") and _sqlite_table_exists(conn, "records"):
            _drop_migration_leftovers(conn)

        tables = ("manifests", "records")
        legacy_columns = {
            "payload_hash",
            "tx_hash",
            "payload_json",
            "creator",
            "user",
            "signature",
            "public_key",
        }
        needs_migration = {
            table: (
                _sqlite_table_exists(conn, table)
                and (
                    bool(_sqlite_table_columns(conn, table) & legacy_columns)
                    or _sqlite_column_types(conn, table).get("timestamp") != "VARCHAR(64)"
                )
            )
            for table in tables
        }
        if needs_migration["manifests"] and _sqlite_table_exists(conn, "records"):
            needs_migration["records"] = True

        if not any(needs_migration.values()):
            return

        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")

        for table, should_migrate in needs_migration.items():
            if should_migrate:
                legacy_table = f"{table}_legacy_payload_migration"
                conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{legacy_table}"')
                conn.exec_driver_sql(f'ALTER TABLE "{table}" RENAME TO "{legacy_table}"')
                _drop_legacy_indexes(conn, legacy_table)

        for index_name in (
            "ix_manifests_manifest_id",
            "ix_records_record_id",
            "ix_records_record_type",
            "ix_records_manifest_id",
        ):
            conn.exec_driver_sql(f'DROP INDEX IF EXISTS "{index_name}"')

        Base.metadata.create_all(bind=conn)

        if needs_migration["manifests"]:
            rows = conn.exec_driver_sql('SELECT * FROM "manifests_legacy_payload_migration"').mappings()
            for row in rows:
                conn.execute(
                    Manifest.__table__.insert().values(
                        manifest_id=row["manifest_id"],
                        good_type=row["good_type"],
                        quantity=row["quantity"],
                        unit=row["unit"],
                        ingredients_json=row["ingredients_json"],
                        origin=row["origin"],
                        sustainability=row["sustainability"],
                        timestamp=_sqlite_timestamp_value(row["timestamp"]),
                        created_at=_parse_sqlite_datetime(row["created_at"]),
                    )
                )
            conn.exec_driver_sql('DROP TABLE "manifests_legacy_payload_migration"')

        if needs_migration["records"]:
            rows = conn.exec_driver_sql('SELECT * FROM "records_legacy_payload_migration"').mappings()
            for row in rows:
                conn.execute(
                    Record.__table__.insert().values(
                        record_id=row["record_id"],
                        record_type=row["record_type"],
                        manifest_id=row["manifest_id"],
                        quantity=row["quantity"],
                        unit=row["unit"],
                        timestamp=_sqlite_timestamp_value(row["timestamp"]),
                        notes=row["notes"],
                        created_at=_parse_sqlite_datetime(row["created_at"]),
                    )
                )
            conn.exec_driver_sql('DROP TABLE "records_legacy_payload_migration"')

        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def init_db():
    """Inicializar as tabelas na base de dados."""
    from app.models.manifest import Manifest
    from app.models.record import Record
    _migrate_sqlite_payload_storage()
    Base.metadata.create_all(bind=engine)
