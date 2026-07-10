import os

from fastapi import FastAPI

from audit_log_lib import AuditLogCreate, AuditLogRepository

app = FastAPI()

repository = AuditLogRepository(
    connection_string=os.environ["MONGO_CONNECTION_STRING"],
    database_name=os.getenv("MONGO_DATABASE_NAME", "audit_db"),
    collection_name=os.getenv("MONGO_COLLECTION_NAME", "audit_trails"),
)


@app.post("/audit")
async def create_audit_log():
    return await repository.create(
        obj_in=AuditLogCreate(
            owner_uid="company-001",
            actor={"username": "alice"},
            entity={"uid": "item-001", "name": "Item 001"},
            entity_type="item",
            action_type="create",
        )
    )


@app.get("/audit")
async def list_audit_logs():
    return await repository.list_paginated_by_owner(
        owner_uid="company-001",
        skip=0,
        limit=20,
    )
