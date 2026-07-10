import asyncio
import os
from datetime import datetime, timedelta

from audit_log_lib import AuditLogCreate, AuditLogRepository


async def main() -> None:
    repository = AuditLogRepository(
        connection_string=os.environ["MONGO_CONNECTION_STRING"],
        database_name=os.getenv("MONGO_DATABASE_NAME", "audit_db"),
        collection_name=os.getenv("MONGO_COLLECTION_NAME", "audit_trails"),
    )

    created = await repository.create(
        obj_in=AuditLogCreate(
            owner_uid="company-001",
            actor={"username": "alice", "name": "Alice", "role": "admin"},
            entity={"uid": "order-123", "name": "Order #123"},
            entity_type="order",
            action_type="create",
        )
    )
    print("created:", created.model_dump() if hasattr(created, "model_dump") else created.dict())

    records = await repository.get_by_owner(
        owner_uid="company-001",
        start_date=datetime.utcnow() - timedelta(days=7),
        end_date=datetime.utcnow(),
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
