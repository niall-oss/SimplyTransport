from datetime import datetime, time
from typing import Annotated

from litestar.params import PathParameter, QueryParameter
from SimplyTransport.api_contracts.enums import DayOfWeek

StartTimeQuery = Annotated[
    time | None,
    QueryParameter(description="Start time, defaults to 10 minutes ago. Example: 10:00:00"),
]
EndTimeQuery = Annotated[
    time | None,
    QueryParameter(description="End time, defaults to 60 minutes from now. Example: 11:00:00"),
]
DayQuery = Annotated[
    DayOfWeek | None,
    QueryParameter(description="Defaults to today."),
]

ScheduledTimePath = Annotated[time, PathParameter(description="HH:MM:SS")]

StartDateTimeQuery = Annotated[
    datetime | None,
    QueryParameter(description="Include records from this time onwards. Example: 2023-10-13T21:34:23Z"),
]
EndDateTimeQuery = Annotated[
    datetime | None,
    QueryParameter(description="Include records up to this time. Example: 2023-10-13T21:34:23Z"),
]
