import os
import importlib

def load_app(tmp_path):
    os.environ.pop("CAMIONES_DATA_DIR", None)
    os.environ["CAMIONES_DB_PATH"] = str(tmp_path / "test_camiones.db")
    if "camiones_gui" in globals():
        importlib.reload(globals()["camiones_gui"])
        return globals()["camiones_gui"]
    module = importlib.import_module("camiones_gui")
    globals()["camiones_gui"] = module
    return module


def test_init_db_and_default_users(tmp_path):
    app = load_app(tmp_path)
    app.init_db()
    users = app.list_users()
    usernames = {u[1] for u in users}
    assert "admin" in usernames
    assert "operador" in usernames


def test_authenticate_user(tmp_path):
    app = load_app(tmp_path)
    app.init_db()
    info = app.authenticate_user("admin", "admin123")
    assert info
    assert info["role"] == "administrador"


def test_user_crud(tmp_path):
    app = load_app(tmp_path)
    app.init_db()
    app.add_user("testuser", "pass123", "operador", "Test User", "123")
    users = app.list_users()
    uid = [u[0] for u in users if u[1] == "testuser"][0]
    app.update_user(uid, "testuser", "administrador", "Test User 2", "456", password="newpass", activo=1)
    info = app.authenticate_user("testuser", "newpass")
    assert info and info["role"] == "administrador"
    app.deactivate_user(uid)
    info = app.authenticate_user("testuser", "newpass")
    assert info is None
    app.reactivate_user(uid)
    info = app.authenticate_user("testuser", "newpass")
    assert info is not None


def test_insert_carga_generates_orden(tmp_path):
    app = load_app(tmp_path)
    app.init_db()
    # Create catalog data
    app.add_vehiculo("ABC123")
    app.add_conductor("Juan", "999")
    app.add_tipo("Carga")
    app.add_ciudad("Bogota")
    app.add_ciudad("Medellin")

    vehiculo_id = app.list_vehiculos()[0][0]
    conductor_id = app.list_conductores()[0][0]
    tipo_id = app.list_tipos()[0][0]
    origen_id = app.list_ciudades()[0][0]
    destino_id = app.list_ciudades()[1][0]

    cid = app.insert_carga((
        vehiculo_id,
        conductor_id,
        tipo_id,
        "2026-01-01",
        "2026-01-02",
        origen_id,
        destino_id,
        None,
        None,
        1000.0,
    ))
    row = app.get_carga(cid)
    assert row[1].startswith("ORD-")


def test_list_cargas_filter(tmp_path):
    app = load_app(tmp_path)
    app.init_db()
    app.add_vehiculo("AAA111")
    app.add_conductor("Ana", "111")
    app.add_tipo("Tipo1")
    app.add_ciudad("C1")
    app.add_ciudad("C2")

    vehiculo_id = app.list_vehiculos()[0][0]
    conductor_id = app.list_conductores()[0][0]
    tipo_id = app.list_tipos()[0][0]
    origen_id = app.list_ciudades()[0][0]
    destino_id = app.list_ciudades()[1][0]

    app.insert_carga((vehiculo_id, conductor_id, tipo_id, "2026-01-01", "2026-01-02", origen_id, destino_id, None, None, 500))
    items = app.list_cargas((vehiculo_id, None, "2026-01-01", "2026-01-01"))
    assert len(items) == 1


def test_list_alertas_marks_future_as_pending(tmp_path):
    app = load_app(tmp_path)
    app.init_db()
    app.add_vehiculo("BBB222")
    app.add_conductor("Luis", "222")
    app.add_tipo("Tipo2")
    app.add_ciudad("C3")
    app.add_ciudad("C4")

    vehiculo_id = app.list_vehiculos()[0][0]
    conductor_id = app.list_conductores()[0][0]
    tipo_id = app.list_tipos()[0][0]
    origen_id = app.list_ciudades()[0][0]
    destino_id = app.list_ciudades()[1][0]

    today = app.datetime.today()
    future_date = today.replace(year=today.year + 1).strftime("%Y-%m-%d")
    past_date = today.replace(year=today.year - 1).strftime("%Y-%m-%d")

    app.insert_carga((vehiculo_id, conductor_id, tipo_id, past_date, future_date, origen_id, destino_id, None, None, 700))
    app.insert_carga((vehiculo_id, conductor_id, tipo_id, past_date, past_date, origen_id, destino_id, None, None, 800))

    estados = [row[-1] for row in app.list_alertas()]
    assert "PENDIENTE" in estados
    assert "ENTREGADO" in estados


def test_default_db_path_uses_shared_windows_dir(monkeypatch, tmp_path):
    os.environ.pop("CAMIONES_DB_PATH", None)
    os.environ.pop("CAMIONES_DATA_DIR", None)
    app = load_app(tmp_path)
    monkeypatch.setattr(app.os, "name", "nt")
    monkeypatch.setattr(app.sys, "frozen", True, raising=False)
    monkeypatch.setenv("SystemDrive", "C:")

    expected_data_dir = app.os.path.normpath("C:/SistemaDeCargas")
    expected_db_path = app.os.path.normpath("C:/SistemaDeCargas/camiones.db")

    assert app.os.path.normpath(app.default_data_dir()) == expected_data_dir
    assert app.os.path.normpath(app.default_db_path()) == expected_db_path


def test_solicitante_crud_for_orden_compra(tmp_path):
    app = load_app(tmp_path)
    app.init_db()

    sid = app.add_solicitante_compra("Maria Perez", "12345", "3001112233", "maria@test.com", "Compras")

    solicitantes = app.list_solicitantes_compra()

    assert any(row[0] == sid and row[1] == "Maria Perez" for row in solicitantes)


def test_insert_orden_compra_generates_consecutivo_and_details(tmp_path):
    app = load_app(tmp_path)
    app.init_db()

    sid = app.add_solicitante_compra("Juan Compras", "999", "3000000000", "juan@test.com", "Supervisor")
    ocid = app.insert_orden_compra(
        "2026-03-29",
        sid,
        None,
        "Entrega en bodega principal",
        "Pago a 30 dias",
        [
            {
                "cantidad": 2,
                "descripcion": "Repuesto industrial",
                "valor_unitario": 1500,
                "valor_total": 3000,
            }
        ],
        "Gerencia",
        "admin",
    )

    rows = app.list_ordenes_compra()
    detail = app.get_orden_compra(ocid)
    items = app.list_orden_compra_items(ocid)

    assert any(row[0] == ocid and row[1].startswith("OC-") for row in rows)
    assert detail[1].startswith("OC-")
    assert detail[3] == "Juan Compras"
    assert detail[13] == "Entrega en bodega principal"
    assert detail[16] == 3000
    assert detail[17] == 3000
    assert len(items) == 1
    assert items[0][2] == "Repuesto industrial"
