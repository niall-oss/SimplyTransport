from advanced_alchemy.exceptions import NotFoundError
from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException
from litestar.params import FromPath
from SimplyTransport.api_contracts.trip_contracts import Trip, TripsWithTotal

from ...domain.trip.trip_repo import TripRepo, provide_trip_repo

__all__ = ["TripController"]


class TripController(Controller):
    dependencies = {"repo": Provide(provide_trip_repo)}

    @get("/{id:str}", summary="Trip by ID", raises=[NotFoundException])
    async def get_trip_by_id(self, repo: NamedDependency[TripRepo], id: FromPath[str]) -> Trip:
        try:
            result = await repo.get(id)
        except NotFoundError as e:
            raise NotFoundException(detail=f"Trip not found with id {id}") from e
        return Trip.model_validate(result)

    @get(
        "/route/{route_id:str}",
        summary="All trips by route id",
        raises=[NotFoundException],
    )
    async def get_all_trips_by_route_id(
        self, repo: NamedDependency[TripRepo], route_id: FromPath[str]
    ) -> list[Trip]:
        try:
            result = await repo.get_many(route_id=route_id)
        except NotFoundError as e:
            raise NotFoundException(detail=f"Trips not found with route id {route_id}") from e
        return [Trip.model_validate(obj) for obj in result]

    @get(
        "/route/count/{route_id:str}",
        summary="All trips by route_id with total count",
        raises=[NotFoundException],
    )
    async def get_all_trips_by_route_id_and_count(
        self, repo: NamedDependency[TripRepo], route_id: FromPath[str]
    ) -> TripsWithTotal:
        try:
            result, total = await repo.get_many_and_count(route_id=route_id)
        except NotFoundError as e:
            raise NotFoundException(detail=f"Trips not found with route id {route_id}") from e
        return TripsWithTotal(total=total, trips=[Trip.model_validate(obj) for obj in result])
