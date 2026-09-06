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
    avg: int = Field(description="Average delay in seconds")
    max: int = Field(description="Largest delay in seconds")
    min: int = Field(description="Smallest delay in seconds")
    standard_deviation: float = Field(description="Standard deviation of delay in seconds")
    p50: int = Field(description="Median delay in seconds")
    p75: int = Field(description="75th percentile delay in seconds")
    p90: int = Field(description="90th percentile delay in seconds")
    samples: int
