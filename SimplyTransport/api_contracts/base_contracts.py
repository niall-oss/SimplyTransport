from pydantic import BaseModel as _BaseModel


class ApiBaseModel(_BaseModel):
    """Pydantic base for API response models."""

    model_config = {"from_attributes": True}
