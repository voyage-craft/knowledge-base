"""Plugin registry model — tracks installed workflow plugins."""

from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PluginRecord(Base):
    """Database record for an installed plugin (builtin or third-party)."""

    __tablename__ = "plugins"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(128), default="")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_compatible: Mapped[bool] = mapped_column(Boolean, default=True)
    compatibility_message: Mapped[str] = mapped_column(String(256), default="")

    install_source: Mapped[str] = mapped_column(
        String(32), default="builtin"
    )  # "builtin" | "upload" | "marketplace"

    config_overrides: Mapped[dict | None] = mapped_column(JSON, default=None)

    installed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Plugin manifest snapshot (full plugin.json at install time)
    manifest_snapshot: Mapped[dict | None] = mapped_column(JSON, default=None)
