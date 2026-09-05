from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException
from litestar.params import FromPath
from SimplyTransport.api_contracts.stop_time_contracts import StopTime

from ...domain.stop_times.stop_time_repo import StopTimeRepo, provide_stop_time_repo

__all__ = ["StopTimeController"]


class StopTimeController(Controller):
    dependencies = {"repo": Provide(provide_stop_time_repo)}

    @get("/trip/{trip_id:str}", summary="StopTimes by trip ID", raises=[NotFoundException])
    async def get_stop_time_by_trip_id(
        self, repo: NamedDependency[StopTimeRepo], trip_id: FromPath[str]
    ) -> list[StopTime]:
        results = await repo.get_many(trip_id=trip_id)
        if results is None or len(results) == 0:
            raise NotFoundException(detail=f"StopTimes not found for trip id {id}")
        return [StopTime.model_validate(obj) for obj in results]

    @get("/stop/{stop_id:str}", summary="StopTimes by stop ID", raises=[NotFoundException])
    async def get_stop_time_by_stop_id(
        self, repo: NamedDependency[StopTimeRepo], stop_id: FromPath[str]
    ) -> list[StopTime]:
        results = await repo.get_many(stop_id=stop_id)
        if results is None or len(results) == 0:
            raise NotFoundException(detail=f"StopTimes not found for stop id {id}")
        return [StopTime.model_validate(obj) for obj in results]
