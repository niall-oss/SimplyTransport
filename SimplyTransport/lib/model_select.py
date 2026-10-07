from typing import cast

from sqlalchemy import Select, select


def select_model[ModelT](model: type[ModelT]) -> Select[tuple[ModelT]]:
    """``select(model)`` typed for Advanced Alchemy's ``statement`` parameter.

    SQLAlchemy 2.1 types a single ORM class as ``Select[Model]``. Advanced Alchemy
    still annotates repository statements as ``Select[tuple[Model]]``.
    """
    return cast(Select[tuple[ModelT]], select(model))
