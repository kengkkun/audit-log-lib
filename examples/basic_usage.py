import asyncio
import os
from datetime import UTC, datetime, timedelta

from pymongo.errors import OperationFailure

from audit_log_lib import AuditLogCreate, AuditLogRepository


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            "Set it to an authenticated MongoDB URI, for example "
            "'mongodb://username:password@localhost:27017/audit_db?authSource=admin'."
        )
    return value


async def main() -> None:
    repository = AuditLogRepository(
        connection_string=_require_env("MONGO_CONNECTION_STRING"),
        database_name=os.getenv("MONGO_DATABASE_NAME", "audit_db"),
        collection_name=os.getenv("MONGO_COLLECTION_NAME", "audit_trails"),
    )

    try:
        created = await repository.create(
            obj_in=AuditLogCreate(
                owner_uid="company-001",
                actor={"username": "alice", "name": "Alice", "role": "admin"},
                entity={"uid": "order-123", "name": "Order #123"},
                entity_type="order",
                action_type="create",
            )
        )
    except OperationFailure as exc:
        if exc.code == 13:
            raise RuntimeError(
                "MongoDB rejected the request because authentication is required. "
                "Update MONGO_CONNECTION_STRING to include valid credentials and authSource."
            ) from exc
        raise

    print("created:", created.model_dump() if hasattr(created, "model_dump") else created.dict())

    records = await repository.get_by_owner(
        owner_uid="company-001",
        start_date=datetime.now(UTC) - timedelta(days=7),
        end_date=datetime.now(UTC),
        skip=0,
        limit=10,
    )
    print("records:", len(records))

    paginated = await repository.list_paginated_by_owner(
        owner_uid="company-001",
        skip=0,
        limit=10,
    )
    payload = paginated.model_dump() if hasattr(paginated, "model_dump") else paginated.dict()
    print("paginated:", payload)


if __name__ == "__main__":
    asyncio.run(main())
