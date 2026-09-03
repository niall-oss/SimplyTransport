from advanced_alchemy.exceptions import NotFoundError
from litestar import Controller, get
from litestar.di import NamedDependency, Provide
from litestar.exceptions import NotFoundException
from litestar.params import FromPath

from SimplyTransport.api_contract.agency import Agency, AgencyWithTotal

from ...domain.agency.repo import AgencyRepository, provide_agency_repo

__all__ = ["AgencyController"]


class AgencyController(Controller):
    dependencies = {"repo": Provide(provide_agency_repo)}

    @get("/", summary="All agencies")
    async def get_all_agencies(self, repo: NamedDependency[AgencyRepository]) -> list[Agency]:
        result = await repo.get_many()
        return [Agency.model_validate(obj) for obj in result]

    @get("/count", summary="All agencies with total count")
    async def get_all_agencies_and_count(self, repo: NamedDependency[AgencyRepository]) -> AgencyWithTotal:
        result, total = await repo.get_many_and_count()
        return AgencyWithTotal(total=total, agencies=[Agency.model_validate(obj) for obj in result])

    @get("/{id:str}", summary="Agency by ID", raises=[NotFoundException])
    async def get_agency_by_id(self, repo: NamedDependency[AgencyRepository], id: FromPath[str]) -> Agency:
        try:
            result = await repo.get(id)
        except NotFoundError as e:
            raise NotFoundException(detail=f"Agency not found with id {id}") from e
        return Agency.model_validate(result)
