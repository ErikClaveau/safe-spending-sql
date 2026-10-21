from pydantic import BaseModel, ConfigDict, Field

from safe_spending.generator.enums import TxCode


class TrapSettings(BaseModel):
    """How many traps the adversarial users get and how big they are (design 5.6)."""

    model_config = ConfigDict(frozen=True)

    extra_per_user: tuple[int, int] = Field(
        description="Every user gets one trap of each type, plus repetitions in this inclusive range."
    )
    amount_eur: tuple[int, int] = Field(
        description="Inclusive range of the amount of each trap, in euros."
    )
    bizum_concept_max_length: int = Field(
        description="Longest free-text concept of a Bizum. Provisional: still an open item in generator-design.md section 8."
    )
    transfer_concept_max_length: int = Field(description="Longest free-text concept of a transfer.")
    canary_prefix: str = Field(description="Fixed start of every canary word.")
    canary_random_length: int = Field(description="Number of random characters at the end of a canary.")

    def concept_limit(
            self,
            tx_code: TxCode
    ) -> int:
        if tx_code == TxCode.BIZUM_IN:
            return self.bizum_concept_max_length
        return self.transfer_concept_max_length
