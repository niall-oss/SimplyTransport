from datetime import datetime, time

from advanced_alchemy.base import BigIntBase
from sqlalchemy import DateTime, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column


class TSStopTimeModel(BigIntBase):
    __tablename__: str = "ts_stop_times"  # type: ignore[assignment]

    Timestamp: Mapped[DateTime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, primary_key=True
    )
    stop_id: Mapped[str] = mapped_column(String(length=1000), nullable=False, index=True)
    route_code: Mapped[str] = mapped_column(String(length=1000), nullable=False, index=True)
    scheduled_time: Mapped[time] = mapped_column(Time, nullable=False, index=True)
    delay_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
