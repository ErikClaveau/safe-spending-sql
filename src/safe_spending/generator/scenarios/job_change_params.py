from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class JobChangeParams(BaseModel):
    change_date: date  # first pay from the new employer
    old_employer: str
    new_employer: str
    old_instalment_eur: Decimal
    new_instalment_eur: Decimal
