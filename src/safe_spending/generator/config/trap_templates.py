from pydantic import BaseModel, ConfigDict, model_validator

from safe_spending.generator.enums import TrapType, TxCode

CANARY_PLACEHOLDER = "{canary}"
TRAP_CHANNELS = (TxCode.BIZUM_IN, TxCode.TRANSFER_IN)  # incoming movements carry a sender's text
MIN_TEMPLATES = 2  # per type and channel, so a user's repeated traps are not all the same text


class TrapTemplates(BaseModel):
    """The repertoire of injection texts, by trap type and channel (traps.yaml).

    Bizum concepts are short, so their templates are short too. Each template holds the canary
    placeholder exactly once.
    """

    model_config = ConfigDict(frozen=True)

    templates: dict[TrapType, dict[TxCode, tuple[str, ...]]]

    @model_validator(mode="after")
    def _repertoire_is_complete_and_well_formed(self) -> "TrapTemplates":
        for trap_type in TrapType:
            for channel in TRAP_CHANNELS:
                texts = self.templates.get(trap_type, {}).get(channel, ())
                if len(texts) < MIN_TEMPLATES:
                    raise ValueError(f"traps.yaml needs at least {MIN_TEMPLATES} {trap_type}/{channel} templates")
                for text in texts:
                    if text.count(CANARY_PLACEHOLDER) != 1:
                        raise ValueError(f"template must hold {CANARY_PLACEHOLDER} exactly once: {text!r}")
        return self

    def for_(
            self,
            trap_type: TrapType,
            tx_code: TxCode
    ) -> tuple[str, ...]:
        return self.templates[trap_type][tx_code]
