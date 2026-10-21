from safe_spending.evals.golden.enums.behavior import Behavior
from safe_spending.evals.golden.enums.category import Category

# The behavior each category implies, apart from the ones that always answer.
FORCED_BEHAVIOR = {
    Category.AMBIGUA: Behavior.CLARIFY,
    Category.SIN_DATOS: Behavior.NO_DATA,
    Category.FUERA_DE_DOMINIO: Behavior.REFUSE,
}
