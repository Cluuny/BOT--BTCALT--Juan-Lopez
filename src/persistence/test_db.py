from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from persistence.db_connection import Database


def run_all_db_tests():
    db = Database()
    try:
        test_connection(db)
        test_tables_exist(db)
        test_table_columns(db, "bot_configs", ["id", "name", "created_at"])
        test_insert_and_query(db)
        test_foreign_keys(db)
        print("\n🎉 Todas las pruebas de base de datos completadas correctamente.")
    except SQLAlchemyError as e:
        print(f"❌ Error SQLAlchemy: {e}")
    except Exception as e:
        print(f"❌ Error general: {e}")


# ---- Tests individuales ----
def test_connection(db):
    session = db.get_session()
    session.execute(text("SELECT 1"))
    session.close()
    print("✅ Conexión básica verificada.")


def test_tables_exist(db):
    session = db.get_session()
    # consulta estática; usar text() por consistencia
    result = session.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    )
    tables = [row[0] for row in result]
    session.close()
    print(f"🗄️ Tablas encontradas: {tables}")


def test_table_columns(db, table_name, expected_columns):
    session = db.get_session()
    # parametrizar el nombre de la tabla para evitar construcción dinámica
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
        print(f"❌ '{table_name}' sin columnas esperadas: {missing}")
    else:
        print(f"✅ '{table_name}' columnas verificadas.")


def test_insert_and_query(db):
    session = db.get_session()
    try:
        session.begin()
        table_name = "bot_configs"

        # Obtener columnas NOT NULL sin default (excluir id)
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
        required_cols = [
            (row[0], row[1]) for row in result if row[0] not in ("id", "created_at")
        ]

        # Preparar columnas/valores para el INSERT; siempre incluimos 'name'
        insert_cols = ["name"]
        value_exprs = [":name"]
        params = {"name": "test_entry"}

        for col, dtype in required_cols:
            if col == "name":
                continue
            insert_cols.append(col)
            # elegir expresión según tipo
            if "timestamp" in dtype:
                # usar función de DB para timestamp
                value_exprs.append("NOW()")
            elif dtype.startswith(
                ("integer", "bigint", "smallint", "numeric", "real", "double")
            ):
                value_exprs.append(f":{col}")
                params[col] = 0
            elif dtype == "boolean":
                value_exprs.append(f":{col}")
                params[col] = False
            else:
                # por defecto tratar como texto
                value_exprs.append(f":{col}")
                params[col] = "test_value"

        columns_sql = ", ".join(insert_cols)
        values_sql = ", ".join(value_exprs)

        session.execute(
            text(f"INSERT INTO {table_name} ({columns_sql}) VALUES ({values_sql})"),
            params,
        )

        # Verificar que la fila insertada existe en la transacción
        result = session.execute(
            text("SELECT name FROM bot_configs WHERE name = :name"),
            {"name": "test_entry"},
        )
        value = result.scalar()
        assert value == "test_entry"
        print("✅ Inserción/lectura exitosas (rollback aplicado).")
    finally:
        session.rollback()
        session.close()


def test_foreign_keys(db):
    session = db.get_session()
    # consulta estática: usar text() por consistencia con las demás
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
        print("🔗 Claves foráneas detectadas:")
        for fk in fks:
            print(f" - {fk.table_name}.{fk.column_name} → {fk.foreign_table_name}")
    else:
        print("⚠️ No hay claves foráneas definidas.")
