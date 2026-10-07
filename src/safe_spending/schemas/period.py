from datetime import date

from safe_spending.schemas._base import _Frozen


class Period(_Frozen):
    start: date
    end: date
