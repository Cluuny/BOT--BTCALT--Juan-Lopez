import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from persistence.db_connection import Database
from utils.logger import Logger

logger = Logger.get_logger(__name__)


def _get_dialect(session):
    try:
        return session.bind.dialect.name
    except Exception:
        try:
            return session.connection().engine.dialect.name
        except Exception:
            return "unknown"


def run_all_db_tests():
    db = Database()
    try:
        test_connection(db)
        test_tables_exist(db)
        test_table_columns(db, "bot_configs", ["id", "name", "created_at"])
        test_insert_and_query(db)
        test_foreign_keys(db)
        logger.info("\n🎉 Todas las pruebas de base de datos completadas correctamente.")
    except SQLAlchemyError as e:
        logger.info(f"❌ Error SQLAlchemy: {e}")
    except Exception as e:
        logger.info(f"❌ Error general: {e}")


# ---- Tests individuales ----
def test_connection(db):
    session = db.get_session()
    session.execute(text("SELECT 1"))
    session.close()
    logger.info("✅ Conexión básica verificada.")


def test_tables_exist(db):
    session = db.get_session()
    dialect = _get_dialect(session)

    if dialect == "sqlite":
        # SQLite: listar tablas desde sqlite_master
        result = session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [row[0] for row in result]
    else:
        # Postgres u otros: usar pg_tables
        result = session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
        tables = [row[0] for row in result]

    session.close()
    logger.info(f"🗄️ Tablas encontradas: {tables}")


@pytest.mark.parametrize("table_name,expected_columns", [("bot_configs", ["id", "name", "created_at"])])
def test_table_columns(db, table_name, expected_columns):
    session = db.get_session()
    dialect = _get_dialect(session)

    if dialect == "sqlite":
        # PRAGMA table_info devuelve (cid, name, type, notnull, dflt_value, pk)
        result = session.execute(text(f"PRAGMA table_info('{table_name}')"))
        columns = [row[1] for row in result]
    else:
        result = session.execute(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = :table"
            ),
            {"table": table_name},
        )
        columns = [row[0] for row in result]

    session.close()
    missing = set(expected_columns) - set(columns)
    if missing:
        logger.info(f"❌ '{table_name}' sin columnas esperadas: {missing}")
    else:
        logger.info(f"✅ '{table_name}' columnas verificadas.")


def test_insert_and_query(db):
    session = db.get_session()
    try:
        session.begin()
        table_name = "bot_configs"
        dialect = _get_dialect(session)

        if dialect == "sqlite":
            # Obtener columnas NOT NULL sin default (excluir id)
            result = session.execute(text(f"PRAGMA table_info('{table_name}')"))
            required_cols = [
                (row[1], row[2]) for row in result if row[3] == 1 and row[4] is None and row[1] not in ("id", "created_at")
            ]
        else:
            result = session.execute(
                text(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = :table
                      AND is_nullable = 'NO'
                      AND column_default IS NULL
                    """
                ),
                {"table": table_name},
            )
            required_cols = [(row[0], row[1]) for row in result if row[0] not in ("id", "created_at")]

        # Preparar columnas/valores para el INSERT; siempre incluimos 'name'
        insert_cols = ["name"]
        value_exprs = [":name"]
        params = {"name": "test_entry"}

        for col, dtype in required_cols:
            if col == "name":
                continue
            insert_cols.append(col)
            if dialect == "sqlite":
                dt = (dtype or "").upper()
                if "INT" in dt or "REAL" in dt or "NUM" in dt or "FLOAT" in dt:
                    value_exprs.append(f":{col}")
                    params[col] = 0
                elif "CHAR" in dt or "TEXT" in dt or "CLOB" in dt:
                    value_exprs.append(f":{col}")
                    params[col] = "test_value"
                elif "DATE" in dt or "TIME" in dt:
                    value_exprs.append("CURRENT_TIMESTAMP")
                else:
                    value_exprs.append(f":{col}")
                    params[col] = "test_value"
            else:
                # elegir expresión según tipo
                if "timestamp" in (dtype or ""):
                    value_exprs.append("NOW()")
                elif dtype.startswith(("integer", "bigint", "smallint", "numeric", "real", "double")):
                    value_exprs.append(f":{col}")
                    params[col] = 0
                elif dtype == "boolean":
                    value_exprs.append(f":{col}")
                    params[col] = False
                else:
                    value_exprs.append(f":{col}")
                    params[col] = "test_value"

        columns_sql = ", ".join(insert_cols)
        values_sql = ", ".join(value_exprs)

        session.execute(
            text(f"INSERT INTO {table_name} ({columns_sql}) VALUES ({values_sql})"),
            params,
        )

        # Verificar que la fila insertada existe en la transacción
        result = session.execute(text("SELECT name FROM bot_configs WHERE name = :name"), {"name": "test_entry"})
        value = result.scalar()
        assert value == "test_entry"
        logger.info("✅ Inserción/lectura exitosas (rollback aplicado).")
    finally:
        session.rollback()
        session.close()


def test_foreign_keys(db):
    session = db.get_session()
    dialect = _get_dialect(session)

    if dialect == "sqlite":
        # listar tablas y usar PRAGMA foreign_key_list
        tables_result = session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        fks = []
        for row in tables_result:
            tbl = row[0]
            fkres = session.execute(text(f"PRAGMA foreign_key_list('{tbl}')"))
            for fkrow in fkres:
                fks.append((tbl, fkrow[3], fkrow[2]))
    else:
        result = session.execute(
            text(
                """
            SELECT tc.table_name, kcu.column_name, ccu.table_name AS foreign_table_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE constraint_type = 'FOREIGN KEY';
            """
            )
        )
        fks = result.fetchall()

    session.close()
    if fks:
        logger.info("🔗 Claves foráneas detectadas:")
        for fk in fks:
            logger.info(f" - {fk}")
    else:
        logger.info("⚠️ No hay claves foráneas definidas.")
