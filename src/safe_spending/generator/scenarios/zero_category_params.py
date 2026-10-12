from pydantic import BaseModel


class ZeroCategoryParams(BaseModel):
    category: str
    group: str
    purchases_removed: int  # proof that the zero is not just a lack of data
