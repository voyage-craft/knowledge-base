from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from datetime import datetime
from typing import Optional


class ApiEndpoint(Base):
    __tablename__ = "api_endpoints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    protocol: Mapped[str] = mapped_column(String(20), nullable=False, default="openai")
    supported_models: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(20), default="healthy")
    stats_json: Mapped[Optional[dict]] = mapped_column(JSON, default=lambda: {
        "total_requests": 0,
        "success_count": 0,
        "avg_latency_ms": 0,
        "p95_latency_ms": 0,
        "consecutive_errors": 0,
        "last_error": None,
        "last_tested_at": None,
    })
    frozen_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=60000)
    # Protocol mode: "auto" (detect on first test), "completions" (Chat Completions API), "responses" (Responses API)
    protocol_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ApiRoutingRule(Base):
    __tablename__ = "api_routing_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    endpoint_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("api_endpoints.id", ondelete="SET NULL"), nullable=True
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_requests_per_minute: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
