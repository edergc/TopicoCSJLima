"""Recursos de identidad visual (logo)."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, FetchedValue, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BrandAsset(Base):
    __tablename__ = "brand_asset"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(40))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("app_user.id"))
