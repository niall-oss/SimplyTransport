"""Import ORM models so SQLAlchemy metadata is complete for Alembic."""

from .agency import agency_model as agency_model
from .calendar import calendar_model as calendar_model
from .calendar_dates import calendar_date_model as calendar_date_model
from .database_statistics import database_statistic_model as database_statistic_model
from .events import event_model as event_model
from .realtime.stop_time import rt_stop_time_model as rt_stop_time_model
from .realtime.trip import rt_trip_model as rt_trip_model
from .realtime.vehicle import rt_vehicle_model as rt_vehicle_model
from .route import route_model as route_model
from .shape import shape_model as shape_model
from .stop import stop_model as stop_model
from .stop_features import stop_feature_model as stop_feature_model
from .stop_times import stop_time_model as stop_time_model
from .trip import trip_model as trip_model
