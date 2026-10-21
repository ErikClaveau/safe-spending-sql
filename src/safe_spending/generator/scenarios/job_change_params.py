from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class JobChangeParams(BaseModel):
    change_date: date = Field(description="First pay from the new employer.")
    old_employer: str = Field(description="Employer before the change.")
    new_employer: str = Field(description="Employer after the change.")
    old_instalment_eur: Decimal = Field(description="Pay instalment before the change, in euros.")
    new_instalment_eur: Decimal = Field(description="Pay instalment after the change, in euros.")
