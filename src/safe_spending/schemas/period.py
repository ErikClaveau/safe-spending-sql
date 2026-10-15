from datetime import date

from pydantic import Field

from safe_spending.schemas._base import _Frozen


class Period(_Frozen):
    start: date = Field(description="First day covered by the dataset.")
    end: date = Field(description="Last day covered by the dataset.")
