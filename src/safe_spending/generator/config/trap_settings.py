from pydantic import BaseModel, ConfigDict

from safe_spending.generator.enums import TxCode


class TrapSettings(BaseModel):
    """How many traps the adversarial users get and how big they are (design 5.6)."""

    model_config = ConfigDict(frozen=True)

    # Every user gets one trap of each type, plus a number of repetitions in this inclusive range.
    extra_per_user: tuple[int, int]
    amount_eur: tuple[int, int]  # inclusive range of the amount of each trap, in euros
    # Longest free-text concept a sender can write. The Bizum value is provisional: it is still
    # an open item in generator-design.md section 8.
    bizum_concept_max_length: int
    transfer_concept_max_length: int
    canary_prefix: str
    canary_random_length: int

    def concept_limit(
            self,
            tx_code: TxCode
    ) -> int:
        if tx_code == TxCode.BIZUM_IN:
            return self.bizum_concept_max_length
        return self.transfer_concept_max_length
