import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Union
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)

def get_db_path(config: RunnableConfig) -> str:
    """Extrae la ruta de la base de datos de la configuración o usa la default."""
    return config["configurable"].get("db_path", "business.db")

@tool
def get_monthly_sales_summary(config: RunnableConfig) -> Dict:
    """
    Obtiene ventas totales, objetivo mensual y estado del mes actual.
    """
    db_path = get_db_path(config)
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            this_month = datetime.now().strftime('%Y-%m')

            cursor.execute(
                "SELECT SUM(amount) as total FROM sales WHERE date LIKE ?",
                (f"{this_month}%",)
            )
            row = cursor.fetchone()
            total = row["total"] or 0

            target = 115000
            status = "En camino" if total < target else "Objetivo cumplido"

            return {
                "ventas_totales": round(total, 2),
                "objetivo_mensual": target,
                "estado": status,
                "moneda": "USD",
                "mes": datetime.now().strftime('%B'),
            }
    except Exception as e:
        logger.error(f"Error en get_monthly_sales_summary: {e}")
        return {"error": "No se pudieron recuperar los datos de ventas actuales."}

@tool
def compare_last_month(config: RunnableConfig) -> Dict:
    """
    Compara el desempeño de ventas del mes actual vs el mes anterior.
    """
    db_path = get_db_path(config)
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            this_m = datetime.now().month
            prev_m = this_m - 1 if this_m > 1 else 12

            # Usamos CAST para asegurar comparación numérica con strftime
            query = "SELECT SUM(amount) FROM sales WHERE CAST(strftime('%m', date) AS INTEGER) = ?"
            
            cursor.execute(query, (this_m,))
            curr_total = cursor.fetchone()[0] or 0

            cursor.execute(query, (prev_m,))
            prev_total = cursor.fetchone()[0] or 0

            if prev_total == 0:
                return {"mensaje": "No hay datos del mes anterior para comparar."}

            diff = ((curr_total - prev_total) / prev_total) * 100
            trend = "alza" if diff > 0 else "baja"

            return {
                "variacion_porcentual": f"{round(diff, 1)}%",
                "tendencia": trend,
                "comparativa": f"Este mes las ventas están un {round(abs(diff), 1)}% por {'encima' if diff > 0 else 'debajo'} del mes pasado."
            }
    except Exception as e:
        logger.error(f"Error en compare_last_month: {e}")
        return {"error": "Error al calcular la comparativa mensual."}

@tool
def top_expense_categories(config: RunnableConfig) -> Union[List[Dict], Dict]:
    """
    Muestra las 3 categorías con mayor gasto en el mes actual.
    """
    db_path = get_db_path(config)
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            this_month = datetime.now().strftime('%Y-%m')

            cursor.execute(
                """
                SELECT category, SUM(amount) as total
                FROM expenses
                WHERE date LIKE ?
                GROUP BY category
                ORDER BY total DESC
                LIMIT 3
                """,
                (f"{this_month}%",)
            )
            results = cursor.fetchall()

            return [
                {"categoria": r[0], "monto": round(r[1], 2)}
                for r in results
            ]
    except Exception as e:
        logger.error(f"Error en top_expense_categories: {e}")
        return {"error": "No se pudo obtener el desglose de gastos."}

@tool
def explain_variance(metric_name: str) -> str:
    """
    Explica la causa raíz de cambios significativos en ventas o gastos basándose en el contexto del negocio.
    """
    # Esta herramienta es de conocimiento de negocio, no requiere DB usualmente
    metric_name = metric_name.lower()
    this_month = datetime.now().month

    if "ventas" in metric_name:
        if this_month == 6:
            return "El aumento de junio se debe a la normalización del stock y promociones de invierno."
        if this_month == 5:
            return "La caída de mayo fue un fenómeno regional por huelgas de transporte que afectaron la logística."
    
    if any(word in metric_name for word in ["gastos", "plata", "egresos"]):
        return "El pico en gastos operativos se debe a la renovación anual de licencias de software y mantenimiento preventivo."

    return "No se reportan eventos extraordinarios para esta métrica en el registro actual."