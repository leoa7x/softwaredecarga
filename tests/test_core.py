import os
import importlib
from pathlib import Path

def load_app(tmp_path):
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
