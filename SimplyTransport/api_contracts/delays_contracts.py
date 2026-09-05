from datetime import datetime, time

from pydantic import AliasChoices, Field, computed_field
from SimplyTransport.api_contracts.base_contracts import ApiBaseModel


class TSStopTime(ApiBaseModel):
    timestamp: datetime = Field(validation_alias=AliasChoices("timestamp", "Timestamp"))
    stop_id: str
    route_code: str
    scheduled_time: time
    delay_in_seconds: int = Field(exclude=True)

    @computed_field(description="Delay in minutes (rounded to 1 decimal place)", return_type=float)
    @property
    def delay_in_minutes(self) -> float:
        return round(self.delay_in_seconds / 60, 1)


class TSStopTimeForGraph(ApiBaseModel):
    timestamp: datetime
    delay_in_seconds: int = Field(exclude=True)

    @computed_field(description="Delay in minutes (rounded to 1 decimal place)", return_type=float)
    @property
    def delay_in_minutes(self) -> float:
        return round(self.delay_in_seconds / 60, 1)


class TSStopTimeDelayAggregated(ApiBaseModel):
    avg: int
    max: int
    min: int
    standard_deviation: float
    p50: int
    p75: int
    p90: int
    samples: int
