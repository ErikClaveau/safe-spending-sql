"""The table names are declared in several places; they must not drift apart."""


from safe_spending.generator.export import SCHEMAS
from safe_spending.generator.simulate import Dataset
from safe_spending.tables import LABELS, OPERATIONAL


def test_operational_and_labels_do_not_overlap():
    assert not set(OPERATIONAL) & set(LABELS)


def test_every_table_has_an_export_schema():
    assert set(SCHEMAS) == set(OPERATIONAL) | set(LABELS)


def test_every_table_is_a_dataset_field():
    assert set(Dataset.model_fields) == set(OPERATIONAL) | set(LABELS)
