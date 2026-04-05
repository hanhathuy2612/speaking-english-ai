from datetime import datetime, timezone
from typing import Annotated

from sqlalchemy.orm import mapped_column

int_pk = Annotated[int, mapped_column(primary_key=True, index=True)]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
