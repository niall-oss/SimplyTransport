from SimplyTransport.api_contracts.base_contracts import ApiBaseModel


class Shape(ApiBaseModel):
    id: int
    shape_id: str
    lat: float
    lon: float
    sequence: int
    distance: float | None
    dataset: str
