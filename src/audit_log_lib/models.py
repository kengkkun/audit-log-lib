from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AuditLogBase(BaseModel):
    owner_uid: Optional[str] = None
    actor: Optional[Dict[str, Any]] = Field(default_factory=dict)
    entity: Optional[Dict[str, Any]] = Field(default_factory=dict)
    entity_type: Optional[str] = None
    action_type: Optional[str] = None


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogRecord(AuditLogBase):
    uid: Optional[str] = None
    created_at: Optional[datetime] = None


class PaginatedAuditLogResult(BaseModel):
    total: int = 0
    items: List[AuditLogRecord] = Field(default_factory=list)
