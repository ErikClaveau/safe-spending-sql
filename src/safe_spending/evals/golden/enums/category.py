from enum import StrEnum


class Category(StrEnum):
    """Question categories of the golden set (plan section 4); the values are the YAML ones."""

    AGREGADO_SIMPLE = "agregado_simple"
    COMPARATIVA_TEMPORAL = "comparativa_temporal"
    RANKING = "ranking"
    FILTRO_COMPUESTO = "filtro_compuesto"
    INGRESOS_VS_GASTOS = "ingresos_vs_gastos"
    RECURRENTES = "recurrentes"
    DIVISA = "divisa"
    DEVOLUCIONES = "devoluciones"
    TRASPASOS = "traspasos"
    AMBIGUA = "ambigua"
    SIN_DATOS = "sin_datos"
    FUERA_DE_DOMINIO = "fuera_de_dominio"
