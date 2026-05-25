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
    """Migrar tabelas SQLite antigas para o formato verificável do repositório."""
    if engine.dialect.name != "sqlite":
        return

    import json

    from shared.hashing import sha256_hex
    from app.models.manifest import Manifest
    from app.models.record import Record

    with engine.begin() as conn:
        if _sqlite_table_exists(conn, "manifests") and _sqlite_table_exists(conn, "records"):
            _drop_migration_leftovers(conn)

        desired_columns = {
            "manifests": {
                "manifest_id",
                "good_type",
                "quantity",
                "unit",
                "ingredients_json",
                "origin",
                "sustainability",
                "owner_user_id",
                "root_manifest_id",
                "parent_manifest_id",
                "source_record_id",
                "creator",
                "timestamp",
                "payload_hash",
                "signature",
                "public_key",
                "manager_signature",
                "manager_public_key",
                "contract_address",
                "tx_hash",
                "created_at",
            },
            "records": {
                "record_id",
                "record_type",
                "manifest_id",
                "quantity",
                "sender_user_id",
                "receiver_user_id",
                "related_record_id",
                "user",
                "timestamp",
                "notes",
                "payload_hash",
                "signature",
                "public_key",
                "manager_signature",
                "manager_public_key",
                "contract_address",
                "tx_hash",
                "created_at",
            },
        }
        obsolete_columns = {
            "manifests": {"payload_json"},
            "records": {"payload_json", "unit"},
        }

        tables = ("manifests", "records")
        needs_migration = {}
        for table in tables:
            columns = _sqlite_table_columns(conn, table) if _sqlite_table_exists(conn, table) else set()
            needs_migration[table] = (
                bool(columns)
                and (
                    not desired_columns[table].issubset(columns)
                    or bool(columns & obsolete_columns[table])
                    or _sqlite_column_types(conn, table).get("timestamp") != "VARCHAR(64)"
                )
            )
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
            "ix_manifests_payload_hash",
            "ix_manifests_tx_hash",
            "ix_manifests_creator",
            "ix_manifests_root_manifest_id",
            "ix_manifests_parent_manifest_id",
            "ix_manifests_source_record_id",
            "ix_records_record_id",
            "ix_records_record_type",
            "ix_records_manifest_id",
            "ix_records_payload_hash",
            "ix_records_tx_hash",
            "ix_records_user",
            "ix_records_related_record_id",
        ):
            conn.exec_driver_sql(f'DROP INDEX IF EXISTS "{index_name}"')

        Base.metadata.create_all(bind=conn)

        if needs_migration["manifests"]:
            rows = conn.exec_driver_sql('SELECT * FROM "manifests_legacy_payload_migration"').mappings()
            for row in rows:
                row_keys = set(row.keys())
                creator = row["creator"] if "creator" in row_keys else ""
                timestamp = _sqlite_timestamp_value(row["timestamp"])
                payload = {
                    "manifest_id": row["manifest_id"],
                    "good_type": row["good_type"],
                    "quantity": row["quantity"],
                    "unit": row["unit"],
                    "ingredients": json.loads(row["ingredients_json"]),
                    "origin": row["origin"],
                    "sustainability": row["sustainability"],
                    "timestamp": timestamp,
                }
                if "owner_user_id" in row_keys and row["owner_user_id"] is not None:
                    payload["owner_user_id"] = row["owner_user_id"]
                if "root_manifest_id" in row_keys and row["root_manifest_id"] is not None:
                    payload["root_manifest_id"] = row["root_manifest_id"]
                if "parent_manifest_id" in row_keys and row["parent_manifest_id"] is not None:
                    payload["parent_manifest_id"] = row["parent_manifest_id"]
                if "source_record_id" in row_keys and row["source_record_id"] is not None:
                    payload["source_record_id"] = row["source_record_id"]
                conn.execute(
                    Manifest.__table__.insert().values(
                        manifest_id=row["manifest_id"],
                        good_type=row["good_type"],
                        quantity=row["quantity"],
                        unit=row["unit"],
                        ingredients_json=row["ingredients_json"],
                        origin=row["origin"],
                        sustainability=row["sustainability"],
                        owner_user_id=row["owner_user_id"] if "owner_user_id" in row_keys else None,
                        root_manifest_id=row["root_manifest_id"] if "root_manifest_id" in row_keys else None,
                        parent_manifest_id=row["parent_manifest_id"] if "parent_manifest_id" in row_keys else None,
                        source_record_id=row["source_record_id"] if "source_record_id" in row_keys else None,
                        creator=creator,
                        timestamp=timestamp,
                        payload_hash=row["payload_hash"] if "payload_hash" in row_keys else sha256_hex(payload),
                        signature=row["signature"] if "signature" in row_keys else "",
                        public_key=row["public_key"] if "public_key" in row_keys else "",
                        manager_signature=row["manager_signature"] if "manager_signature" in row_keys else "",
                        manager_public_key=row["manager_public_key"] if "manager_public_key" in row_keys else "",
                        contract_address=row["contract_address"] if "contract_address" in row_keys else "",
                        tx_hash=row["tx_hash"] if "tx_hash" in row_keys else "",
                        created_at=_parse_sqlite_datetime(row["created_at"]),
                    )
                )
            conn.exec_driver_sql('DROP TABLE "manifests_legacy_payload_migration"')

        if needs_migration["records"]:
            rows = conn.exec_driver_sql('SELECT * FROM "records_legacy_payload_migration"').mappings()
            for row in rows:
                row_keys = set(row.keys())
                user = row["user"] if "user" in row_keys else ""
                timestamp = _sqlite_timestamp_value(row["timestamp"])
                payload = {
                    "record_id": row["record_id"],
                    "record_type": row["record_type"],
                    "manifest_id": row["manifest_id"],
                    "quantity": row["quantity"],
                    "timestamp": timestamp,
                    "notes": row["notes"],
                }
                if row_keys >= {"sender_user_id"} and row["sender_user_id"] is not None:
                    payload["sender_user_id"] = row["sender_user_id"]
                if row_keys >= {"receiver_user_id"} and row["receiver_user_id"] is not None:
                    payload["receiver_user_id"] = row["receiver_user_id"]
                if row_keys >= {"related_record_id"} and row["related_record_id"] is not None:
                    payload["related_record_id"] = row["related_record_id"]
                conn.execute(
                    Record.__table__.insert().values(
                        record_id=row["record_id"],
                        record_type=row["record_type"],
                        manifest_id=row["manifest_id"],
                        quantity=row["quantity"],
                        sender_user_id=row["sender_user_id"] if "sender_user_id" in row_keys else None,
                        receiver_user_id=row["receiver_user_id"] if "receiver_user_id" in row_keys else None,
                        related_record_id=row["related_record_id"] if "related_record_id" in row_keys else None,
                        user=user,
                        timestamp=timestamp,
                        notes=row["notes"],
                        payload_hash=row["payload_hash"] if "payload_hash" in row_keys else sha256_hex(payload),
                        signature=row["signature"] if "signature" in row_keys else "",
                        public_key=row["public_key"] if "public_key" in row_keys else "",
                        manager_signature=row["manager_signature"] if "manager_signature" in row_keys else "",
                        manager_public_key=row["manager_public_key"] if "manager_public_key" in row_keys else "",
                        contract_address=row["contract_address"] if "contract_address" in row_keys else "",
                        tx_hash=row["tx_hash"] if "tx_hash" in row_keys else "",
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
