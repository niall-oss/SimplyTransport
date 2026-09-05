from SimplyTransport.api_contracts.base_contracts import ApiBaseModel


class Agency(ApiBaseModel):
    id: str
    name: str
    url: str
    timezone: str
    dataset: str


class AgencyWithTotal(ApiBaseModel):
    total: int
    agencies: list[Agency]
