from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from netsmoke.db.base import Base


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    host: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(1024), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    measurement_rounds: Mapped[list["MeasurementRound"]] = relationship(back_populates="target")


class MeasurementRound(Base):
    __tablename__ = "measurement_rounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sent: Mapped[int] = mapped_column(Integer)
    received: Mapped[int] = mapped_column(Integer)
    loss_pct: Mapped[float] = mapped_column(Float)
    median_rtt_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    target: Mapped[Target] = relationship(back_populates="measurement_rounds")
    ping_samples: Mapped[list["PingSample"]] = relationship(back_populates="measurement_round")


class PingSample(Base):
    __tablename__ = "ping_samples"
    __table_args__ = (UniqueConstraint("measurement_round_id", "sample_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    measurement_round_id: Mapped[int] = mapped_column(ForeignKey("measurement_rounds.id"), index=True)
    sample_index: Mapped[int] = mapped_column(Integer)
    rtt_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    measurement_round: Mapped[MeasurementRound] = relationship(back_populates="ping_samples")
