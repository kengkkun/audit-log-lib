# `library.audit-log`

Lightweight async audit log library for MongoDB. It supports:

- create audit log records
- query audit log records as a list
- query audit log records with pagination
- custom MongoDB queries with automatic ISO datetime conversion

## Installation

```bash
pip install library.audit-log
```

For local development inside this repository:

```bash
cd audit-log-lib
python -m build
```

Install development dependencies:

```bash
pip install -e .[dev]
```

## Configuration

The library connects to MongoDB using a connection string.

### Required config

- `connection_string`: MongoDB connection string

Example:

```env
MONGO_CONNECTION_STRING=mongodb://username:password@localhost:27017/audit_db?authSource=admin
```

### Optional config

- `database_name`: Explicit database name. If omitted, the library uses the database from the connection string.
- `collection_name`: MongoDB collection name. Default is `audit_trails`.

## Data model

Each audit log record supports these fields:

```json
{
  "owner_uid": "company-001",
  "actor": {
    "username": "alice",
    "name": "Alice",
    "role": "admin"
  },
  "entity": {
    "uid": "order-123",
    "name": "Order #123"
  },
  "entity_type": "order",
  "action_type": "create"
}
```

The library automatically adds:

- `uid`
- `created_at`

## Basic usage

```python
import os

from audit_log_lib import AuditLogCreate, AuditLogRepository


repository = AuditLogRepository(
    connection_string=os.environ["MONGO_CONNECTION_STRING"],
    database_name="audit_db",
    collection_name="audit_trails",
)


async def create_log():
    result = await repository.create(
        obj_in=AuditLogCreate(
            owner_uid="company-001",
            actor={
                "username": "alice",
                "name": "Alice",
                "role": "admin",
            },
            entity={
                "uid": "order-123",
                "name": "Order #123",
            },
            entity_type="order",
            action_type="create",
        )
    )
    return result
```

## Get by uid

```python
async def get_one(uid: str):
    return await repository.get_by_uid(uid=uid)
```

## Get as list

```python
from datetime import datetime, timedelta


async def get_logs():
    return await repository.get_by_owner(
        owner_uid="company-001",
        username="alice",
        start_date=datetime.utcnow() - timedelta(days=7),
        end_date=datetime.utcnow(),
        search_keyword="order",
        skip=0,
        limit=50,
    )
```

## Get with pagination

If you want both `items` and `total`, use the paginated methods.

```python
async def get_logs_paginated():
    result = await repository.list_paginated_by_owner(
        owner_uid="company-001",
        entity_type="order",
        action_type="create",
        skip=0,
        limit=20,
    )

    print(result.total)
    print(result.items)
    return result
```

## Custom query with pagination

```python
async def get_custom_logs():
    return await repository.list_custom_paginated(
        owner_uid="company-001",
        custom_query={
            "entity_type": "order",
            "created_at": {
                "$gte": "2024-01-01T00:00:00.000Z",
                "$lte": "2024-12-31T23:59:59.000Z",
            },
            "$or": [
                {"actor.username": "alice"},
                {"entity.name": {"$regex": "Order", "$options": "i"}},
            ],
        },
        skip=0,
        limit=20,
    )
```

The library will automatically convert ISO datetime strings under `$gte`, `$lte`, `$gt`, and `$lt` into Python `datetime` objects before sending the query to MongoDB.

## FastAPI example

```python
import os

from fastapi import FastAPI
from audit_log_lib import AuditLogCreate, AuditLogRepository


app = FastAPI()

audit_repository = AuditLogRepository(
    connection_string=os.environ["MONGO_CONNECTION_STRING"],
    database_name="audit_db",
)


@app.post("/audit")
async def create_audit_log():
    return await audit_repository.create(
        obj_in=AuditLogCreate(
            owner_uid="company-001",
            actor={"username": "alice"},
            entity={"uid": "item-001", "name": "Item 001"},
            entity_type="item",
            action_type="create",
        )
    )
```

See runnable examples in:

- `examples/basic_usage.py`
- `examples/fastapi_example.py`

## Tests

Run tests:

```bash
cd audit-log-lib
pytest
```

Main coverage included in `tests/test_repository.py`:

- create log
- get by uid
- get list by owner
- pagination with total/items
- custom query with ISO datetime conversion