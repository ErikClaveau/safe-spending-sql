from enum import StrEnum


class ScenarioType(StrEnum):
    """Scripted scenarios (design 5.5); the values are the `type` column of `scenarios`."""

    SUBSCRIPTION_CHANGES = "subscription_changes"
    JOB_CHANGE = "job_change"
    RECENT_SIGNUP = "recent_signup"
    ZERO_CATEGORY = "zero_category"
    ANOMALOUS_MONTH = "anomalous_month"
