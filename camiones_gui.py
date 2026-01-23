import os
import sys
import tempfile
import subprocess
import sqlite3
import hashlib
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
try:
    from tkcalendar import Calendar
except Exception:
    Calendar = None

APP_NAME = "Sistema de Cargas"
COLOR_BG = "#e9edf5"
COLOR_ACCENT = "#ff5a70"
COLOR_DARK = "#3b3f4a"
COLOR_HI = "#f4b13d"

CONFIG_DEFAULTS = {
    "encabezado": "RECIBO DE CARGA",
    "logo_path": "",
    "nit": "",
    "direccion": "",
    "telefono": "",
}

DEFAULT_USERS = [
    ("admin", "admin123", "administrador", "Administrador", ""),
    ("operador", "operador123", "operador", "Operador", ""),
]


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(rel):
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(app_dir(), rel)


DB_PATH = os.path.join(app_dir(), "camiones.db")


# ---- DB helpers ----

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def table_columns(conn, table):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def get_or_create(conn, table, field, value):
    cur = conn.execute(f"SELECT id FROM {table} WHERE {field} = ?", (value,))
    row = cur.fetchone()
    if row:
        return row[0]
    conn.execute(f"INSERT INTO {table} ({field}) VALUES (?)", (value,))
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

def hash_password(password, salt):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def init_db():
    with connect_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conductores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                cedula TEXT UNIQUE
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vehiculos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                placa TEXT NOT NULL UNIQUE
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tipos_carga (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ciudades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bodegas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                ciudad_id INTEGER,
                FOREIGN KEY (ciudad_id) REFERENCES ciudades(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL,
                nombre TEXT,
                cedula TEXT,
                activo INTEGER DEFAULT 1
            );
            """
        )

        # Migration if old schema exists
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cargas'"
        )
        has_cargas = cur.fetchone() is not None
        if has_cargas:
            cols = table_columns(conn, "cargas")
            if "vehiculo_id" not in cols:
                legacy_name = "cargas_legacy"
                conn.execute(f"ALTER TABLE cargas RENAME TO {legacy_name}")
                conn.execute(
                    """
                    CREATE TABLE cargas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        orden TEXT UNIQUE,
                        vehiculo_id INTEGER NOT NULL,
                        conductor_id INTEGER NOT NULL,
                        tipo_carga_id INTEGER NOT NULL,
                        fecha_carga TEXT NOT NULL,
                        fecha_descarga TEXT NOT NULL,
                        origen_ciudad_id INTEGER NOT NULL,
                        destino_ciudad_id INTEGER NOT NULL,
                        bodega_origen_id INTEGER,
                        bodega_destino_id INTEGER,
                        peso REAL NOT NULL,
                        FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id),
                        FOREIGN KEY (conductor_id) REFERENCES conductores(id),
                        FOREIGN KEY (tipo_carga_id) REFERENCES tipos_carga(id),
                        FOREIGN KEY (origen_ciudad_id) REFERENCES ciudades(id),
                        FOREIGN KEY (destino_ciudad_id) REFERENCES ciudades(id),
                        FOREIGN KEY (bodega_origen_id) REFERENCES bodegas(id),
                        FOREIGN KEY (bodega_destino_id) REFERENCES bodegas(id)
                    );
                    """
                )
                cur = conn.execute(
                    f"SELECT placa, peso, conductor, tipo_carga, fecha_carga, fecha_descarga, origen, destino FROM {legacy_name}"
                )
                rows = cur.fetchall()
                for placa, peso, conductor, tipo_carga, fecha_carga, fecha_descarga, origen, destino in rows:
                    vehiculo_id = get_or_create(conn, "vehiculos", "placa", placa)
                    conductor_id = get_or_create(conn, "conductores", "nombre", conductor)
                    tipo_id = get_or_create(conn, "tipos_carga", "nombre", tipo_carga)
                    origen_id = get_or_create(conn, "ciudades", "nombre", origen)
                    destino_id = get_or_create(conn, "ciudades", "nombre", destino)
                    conn.execute(
                        """
                        INSERT INTO cargas (
                            vehiculo_id, conductor_id, tipo_carga_id,
                            fecha_carga, fecha_descarga,
                            origen_ciudad_id, destino_ciudad_id,
                            bodega_origen_id, bodega_destino_id, peso
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
                        """,
                        (
                            vehiculo_id,
                            conductor_id,
                            tipo_id,
                            fecha_carga,
                            fecha_descarga,
                            origen_id,
                            destino_id,
                            peso,
                        ),
                    )
                conn.commit()
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cargas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    orden TEXT UNIQUE,
                    vehiculo_id INTEGER NOT NULL,
                    conductor_id INTEGER NOT NULL,
                    tipo_carga_id INTEGER NOT NULL,
                    fecha_carga TEXT NOT NULL,
                    fecha_descarga TEXT NOT NULL,
                    origen_ciudad_id INTEGER NOT NULL,
                    destino_ciudad_id INTEGER NOT NULL,
                    bodega_origen_id INTEGER,
                    bodega_destino_id INTEGER,
                    peso REAL NOT NULL,
                    FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id),
                    FOREIGN KEY (conductor_id) REFERENCES conductores(id),
                    FOREIGN KEY (tipo_carga_id) REFERENCES tipos_carga(id),
                    FOREIGN KEY (origen_ciudad_id) REFERENCES ciudades(id),
                    FOREIGN KEY (destino_ciudad_id) REFERENCES ciudades(id),
                    FOREIGN KEY (bodega_origen_id) REFERENCES bodegas(id),
                    FOREIGN KEY (bodega_destino_id) REFERENCES bodegas(id)
                );
                """
            )
        # Ensure orden column exists and backfill
        cols = table_columns(conn, "cargas")
        if "orden" not in cols:
            conn.execute("ALTER TABLE cargas ADD COLUMN orden TEXT")
        cur = conn.execute("SELECT id FROM cargas WHERE orden IS NULL OR orden = ''")
        rows = cur.fetchall()
        for (cid,) in rows:
            orden = generate_orden(cid)
            conn.execute("UPDATE cargas SET orden = ? WHERE id = ?", (orden, cid))
        # Config defaults
        for k, v in CONFIG_DEFAULTS.items():
            cur = conn.execute("SELECT value FROM config WHERE key = ?", (k,))
            if cur.fetchone() is None:
                conn.execute("INSERT INTO config (key, value) VALUES (?, ?)", (k, v))
        # Default users
        # Add missing columns to users table if needed
        user_cols = table_columns(conn, "users")
        if "nombre" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN nombre TEXT")
        if "cedula" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN cedula TEXT")
        if "activo" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN activo INTEGER DEFAULT 1")

        for username, password, role, nombre, cedula in DEFAULT_USERS:
            cur = conn.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cur.fetchone() is None:
                salt = os.urandom(8).hex()
                pwd_hash = hash_password(password, salt)
                conn.execute(
                    "INSERT INTO users (username, password_hash, salt, role, nombre, cedula, activo) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1)",
                    (username, pwd_hash, salt, role, nombre, cedula or None),
                )
        conn.commit()


def parse_date(val):
    datetime.strptime(val, "%Y-%m-%d")
    return val


def generate_orden(cid):
    today = datetime.today().strftime("%Y%m%d")
    return f"ORD-{today}-{cid:06d}"


def get_config(key):
    with connect_db() as conn:
        cur = conn.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else CONFIG_DEFAULTS.get(key, "")


def set_config(key, value):
    with connect_db() as conn:
        conn.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()

def authenticate_user(username, password):
    with connect_db() as conn:
        cur = conn.execute(
            "SELECT password_hash, salt, role, COALESCE(nombre,''), COALESCE(cedula,''), activo "
            "FROM users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        if not row:
            return None
        pwd_hash, salt, role, nombre, cedula, activo = row
        if not activo:
            return None
        if hash_password(password, salt) == pwd_hash:
            return {"username": username, "role": role, "nombre": nombre, "cedula": cedula}
    return None


def list_users():
    with connect_db() as conn:
        cur = conn.execute(
            "SELECT id, username, COALESCE(nombre,''), COALESCE(cedula,''), role, activo "
            "FROM users ORDER BY username"
        )
        return cur.fetchall()


def add_user(username, password, role, nombre, cedula):
    salt = os.urandom(8).hex()
    pwd_hash = hash_password(password, salt)
    with connect_db() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, nombre, cedula, activo) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (username, pwd_hash, salt, role, nombre, cedula or None),
        )
        conn.commit()


def update_user(uid, username, role, nombre, cedula, password=None, activo=1):
    with connect_db() as conn:
        if password:
            salt = os.urandom(8).hex()
            pwd_hash = hash_password(password, salt)
            conn.execute(
                "UPDATE users SET username=?, role=?, nombre=?, cedula=?, activo=?, "
                "password_hash=?, salt=? WHERE id=?",
                (username, role, nombre, cedula or None, activo, pwd_hash, salt, uid),
            )
        else:
            conn.execute(
                "UPDATE users SET username=?, role=?, nombre=?, cedula=?, activo=? WHERE id=?",
                (username, role, nombre, cedula or None, activo, uid),
            )
        conn.commit()


def deactivate_user(uid):
    with connect_db() as conn:
        conn.execute("UPDATE users SET activo=0 WHERE id=?", (uid,))
        conn.commit()


def reactivate_user(uid):
    with connect_db() as conn:
        conn.execute("UPDATE users SET activo=1 WHERE id=?", (uid,))
        conn.commit()


# ---- Catalog queries ----

def list_conductores():
    with connect_db() as conn:
        cur = conn.execute(
            "SELECT id, nombre, COALESCE(cedula, '') FROM conductores ORDER BY nombre"
        )
        return cur.fetchall()


def list_vehiculos():
    with connect_db() as conn:
        cur = conn.execute("SELECT id, placa FROM vehiculos ORDER BY placa")
        return cur.fetchall()


def list_tipos():
    with connect_db() as conn:
        cur = conn.execute("SELECT id, nombre FROM tipos_carga ORDER BY nombre")
        return cur.fetchall()


def list_ciudades():
    with connect_db() as conn:
        cur = conn.execute("SELECT id, nombre FROM ciudades ORDER BY nombre")
        return cur.fetchall()


def list_bodegas():
    with connect_db() as conn:
        cur = conn.execute(
            """
            SELECT b.id, b.nombre, COALESCE(c.nombre, '')
            FROM bodegas b
            LEFT JOIN ciudades c ON c.id = b.ciudad_id
            ORDER BY b.nombre
            """
        )
        return cur.fetchall()


def add_conductor(nombre, cedula):
    with connect_db() as conn:
        conn.execute(
            "INSERT INTO conductores (nombre, cedula) VALUES (?, ?)", (nombre, cedula or None)
        )
        conn.commit()


def update_conductor(cid, nombre, cedula):
    with connect_db() as conn:
        conn.execute(
            "UPDATE conductores SET nombre = ?, cedula = ? WHERE id = ?",
            (nombre, cedula or None, cid),
        )
        conn.commit()


def delete_conductor(cid):
    with connect_db() as conn:
        conn.execute("DELETE FROM conductores WHERE id = ?", (cid,))
        conn.commit()


def add_vehiculo(placa):
    with connect_db() as conn:
        conn.execute("INSERT INTO vehiculos (placa) VALUES (?)", (placa,))
        conn.commit()


def update_vehiculo(vid, placa):
    with connect_db() as conn:
        conn.execute("UPDATE vehiculos SET placa = ? WHERE id = ?", (placa, vid))
        conn.commit()


def delete_vehiculo(vid):
    with connect_db() as conn:
        conn.execute("DELETE FROM vehiculos WHERE id = ?", (vid,))
        conn.commit()


def add_tipo(nombre):
    with connect_db() as conn:
        conn.execute("INSERT INTO tipos_carga (nombre) VALUES (?)", (nombre,))
        conn.commit()


def update_tipo(tid, nombre):
    with connect_db() as conn:
        conn.execute("UPDATE tipos_carga SET nombre = ? WHERE id = ?", (nombre, tid))
        conn.commit()


def delete_tipo(tid):
    with connect_db() as conn:
        conn.execute("DELETE FROM tipos_carga WHERE id = ?", (tid,))
        conn.commit()


def add_ciudad(nombre):
    with connect_db() as conn:
        conn.execute("INSERT INTO ciudades (nombre) VALUES (?)", (nombre,))
        conn.commit()


def update_ciudad(cid, nombre):
    with connect_db() as conn:
        conn.execute("UPDATE ciudades SET nombre = ? WHERE id = ?", (nombre, cid))
        conn.commit()


def delete_ciudad(cid):
    with connect_db() as conn:
        conn.execute("DELETE FROM ciudades WHERE id = ?", (cid,))
        conn.commit()


def add_bodega(nombre, ciudad_id):
    with connect_db() as conn:
        conn.execute(
            "INSERT INTO bodegas (nombre, ciudad_id) VALUES (?, ?)", (nombre, ciudad_id)
        )
        conn.commit()


def update_bodega(bid, nombre, ciudad_id):
    with connect_db() as conn:
        conn.execute(
            "UPDATE bodegas SET nombre = ?, ciudad_id = ? WHERE id = ?",
            (nombre, ciudad_id, bid),
        )
        conn.commit()


def delete_bodega(bid):
    with connect_db() as conn:
        conn.execute("DELETE FROM bodegas WHERE id = ?", (bid,))
        conn.commit()


# ---- Cargas ----
def list_cargas(filters):
    vehiculo_id, tipo_id, f_ini, f_fin = filters
    clauses = []
    params = []

    if vehiculo_id:
        clauses.append("vehiculo_id = ?")
        params.append(vehiculo_id)
    if tipo_id:
        clauses.append("tipo_carga_id = ?")
        params.append(tipo_id)
    if f_ini:
        clauses.append("fecha_carga >= ?")
        params.append(f_ini)
    if f_fin:
        clauses.append("fecha_carga <= ?")
        params.append(f_fin)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    with connect_db() as conn:
        cur = conn.execute(
            f"""
            SELECT ca.id, ca.orden, v.placa, c.nombre, t.nombre, ca.fecha_carga, ca.fecha_descarga, ca.peso
            FROM cargas ca
            JOIN vehiculos v ON v.id = ca.vehiculo_id
            JOIN conductores c ON c.id = ca.conductor_id
            JOIN tipos_carga t ON t.id = ca.tipo_carga_id
            {where}
            ORDER BY ca.fecha_carga DESC, ca.id DESC
            """,
            params,
        )
        return cur.fetchall()


def delete_carga(cid):
    with connect_db() as conn:
        conn.execute("DELETE FROM cargas WHERE id = ?", (cid,))
        conn.commit()

def get_carga(cid):
    with connect_db() as conn:
        cur = conn.execute(
            """
            SELECT ca.id, ca.orden, v.placa, c.nombre, COALESCE(c.cedula, ''), t.nombre,
                   ca.fecha_carga, ca.fecha_descarga,
                   co.nombre, cd.nombre,
                   bo.nombre, bd.nombre,
                   ca.peso
            FROM cargas ca
            JOIN vehiculos v ON v.id = ca.vehiculo_id
            JOIN conductores c ON c.id = ca.conductor_id
            JOIN tipos_carga t ON t.id = ca.tipo_carga_id
            JOIN ciudades co ON co.id = ca.origen_ciudad_id
            JOIN ciudades cd ON cd.id = ca.destino_ciudad_id
            LEFT JOIN bodegas bo ON bo.id = ca.bodega_origen_id
            LEFT JOIN bodegas bd ON bd.id = ca.bodega_destino_id
            WHERE ca.id = ?
            """,
            (cid,),
        )
        return cur.fetchone()


def update_carga(cid, data):
    with connect_db() as conn:
        conn.execute(
            """
            UPDATE cargas
            SET vehiculo_id = ?, conductor_id = ?, tipo_carga_id = ?,
                fecha_carga = ?, fecha_descarga = ?,
                origen_ciudad_id = ?, destino_ciudad_id = ?,
                bodega_origen_id = ?, bodega_destino_id = ?, peso = ?
            WHERE id = ?
            """,
            (*data, cid),
        )
        conn.commit()

def insert_carga(data):
    with connect_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO cargas (
                vehiculo_id, conductor_id, tipo_carga_id,
                fecha_carga, fecha_descarga,
                origen_ciudad_id, destino_ciudad_id,
                bodega_origen_id, bodega_destino_id, peso
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
        )
        cid = cur.lastrowid
        orden = generate_orden(cid)
        conn.execute("UPDATE cargas SET orden = ? WHERE id = ?", (orden, cid))
        conn.commit()
        return cid


def query_stats(filters):
    vehiculo_id, tipo_id, f_ini, f_fin = filters
    clauses = []
    params = []

    if vehiculo_id:
        clauses.append("vehiculo_id = ?")
        params.append(vehiculo_id)
    if tipo_id:
        clauses.append("tipo_carga_id = ?")
        params.append(tipo_id)
    if f_ini:
        clauses.append("fecha_carga >= ?")
        params.append(f_ini)
    if f_fin:
        clauses.append("fecha_carga <= ?")
        params.append(f_fin)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    with connect_db() as conn:
        cur = conn.cursor()

        cur.execute(
            f"""
            SELECT COUNT(*), SUM(peso), AVG(peso)
            FROM cargas
            {where}
            """,
            params,
        )
        total_reg, total_kg, avg_kg = cur.fetchone()

        cur.execute(
            f"""
            SELECT fecha_carga, SUM(peso)
            FROM cargas
            {where}
            GROUP BY fecha_carga
            ORDER BY fecha_carga
            """,
            params,
        )
        por_dia = cur.fetchall()

        cur.execute(
            f"""
            SELECT SUBSTR(fecha_carga, 1, 7) AS mes, SUM(peso), AVG(peso)
            FROM cargas
            {where}
            GROUP BY mes
            ORDER BY mes
            """,
            params,
        )
        por_mes = cur.fetchall()

        cur.execute(
            f"""
            SELECT SUBSTR(fecha_carga, 1, 4) AS year, SUM(peso), AVG(peso)
            FROM cargas
            {where}
            GROUP BY year
            ORDER BY year
            """,
            params,
        )
        por_year = cur.fetchall()

        cur.execute(
            f"""
            SELECT MAX(peso), MIN(peso)
            FROM cargas
            {where}
            """,
            params,
        )
        max_kg, min_kg = cur.fetchone()

        cur.execute(
            f"""
            SELECT t.nombre, COUNT(*) AS c
            FROM cargas c
            JOIN tipos_carga t ON t.id = c.tipo_carga_id
            {where}
            GROUP BY t.nombre
            ORDER BY c DESC
            """,
            params,
        )
        tipos = cur.fetchall()

    return {
        "total_reg": total_reg or 0,
        "total_kg": total_kg or 0,
        "avg_kg": avg_kg or 0,
        "por_dia": por_dia,
        "por_mes": por_mes,
        "por_year": por_year,
        "max_kg": max_kg or 0,
        "min_kg": min_kg or 0,
        "tipos": tipos,
    }


def list_alertas():
    hoy = datetime.today().strftime("%Y-%m-%d")
    with connect_db() as conn:
        cur = conn.execute(
            """
            SELECT v.placa, c.nombre, t.nombre, ca.fecha_carga, ca.fecha_descarga, ca.peso
            FROM cargas ca
            JOIN vehiculos v ON v.id = ca.vehiculo_id
            JOIN conductores c ON c.id = ca.conductor_id
            JOIN tipos_carga t ON t.id = ca.tipo_carga_id
            ORDER BY ca.fecha_descarga DESC
            """
        )
        rows = cur.fetchall()

    alerta = []
    for placa, conductor, tipo, f_carga, f_descarga, peso in rows:
        estado = "ENTREGADO" if f_descarga > hoy else "PENDIENTE"
        alerta.append((placa, conductor, tipo, f_carga, f_descarga, peso, estado))
    return alerta


# ---- UI ----
class SearchDialog(tk.Toplevel):
    def __init__(self, parent, items, title="Buscar"):
        super().__init__(parent)
        self.title(title)
        self.geometry("420x360")
        self.resizable(False, False)
        self.selected = None
        self.items = items

        ttk.Label(self, text="Buscar").pack(anchor="w", padx=10, pady=(10, 0))
        self.q = ttk.Entry(self, width=40)
        self.q.pack(padx=10, pady=6)
        self.q.bind("<KeyRelease>", self._filter)

        self.listbox = tk.Listbox(self, height=14)
        self.listbox.pack(fill="both", expand=True, padx=10, pady=6)
        self.listbox.bind("<Double-1>", self._choose)

        btns = ttk.Frame(self)
        btns.pack(pady=6)
        ttk.Button(btns, text="Seleccionar", command=self._choose).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="left", padx=6)

        self._render(items)
        self.q.focus_set()

    def _render(self, items):
        self.listbox.delete(0, tk.END)
        for _id, label in items:
            self.listbox.insert(tk.END, label)

    def _filter(self, _event=None):
        term = self.q.get().strip().lower()
        if not term:
            self._render(self.items)
            return
        filtered = [(i, l) for i, l in self.items if term in l.lower()]
        self._render(filtered)

    def _choose(self, _event=None):
        idx = self.listbox.curselection()
        if not idx:
            return
        label = self.listbox.get(idx[0])
        self.selected = label
        self.destroy()


def login_dialog():
    root = tk.Tk()
    root.title("Inicio de sesión")
    root.geometry("360x220")
    root.resizable(False, False)

    frm = ttk.Frame(root, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text=APP_NAME, font=("Helvetica", 14, "bold")).pack(pady=(0, 8))

    ttk.Label(frm, text="Usuario").pack(anchor="w")
    user_entry = ttk.Entry(frm, width=30)
    user_entry.pack(pady=4)

    ttk.Label(frm, text="Contraseña").pack(anchor="w")
    pass_entry = ttk.Entry(frm, width=30, show="*")
    pass_entry.pack(pady=4)

    note = "Usuarios por defecto: admin/admin123, operador/operador123"
    ttk.Label(frm, text=note, foreground="#555").pack(pady=(6, 0))

    result = {"username": None, "role": None, "nombre": None, "cedula": None}

    def do_login():
        username = user_entry.get().strip()
        password = pass_entry.get().strip()
        if not username or not password:
            messagebox.showerror("Error", "Usuario y contraseña requeridos.")
            return
        info = authenticate_user(username, password)
        if not info:
            messagebox.showerror("Error", "Credenciales inválidas.")
            return
        result.update(info)
        root.destroy()

    ttk.Button(frm, text="Ingresar", command=do_login).pack(pady=10)

    user_entry.focus_set()
    root.bind("<Return>", lambda _e: do_login())
    root.mainloop()
    if result["username"]:
        return result
    return None


class App(tk.Tk):
    def __init__(self, user_info=None):
        super().__init__()
        self.user_info = user_info or {"username": "N/A", "role": "N/A"}
        self.title(APP_NAME)
        self.geometry("1020x740")
        self.resizable(False, False)
        self.configure(bg=COLOR_BG)
        self._set_icon()
        self._build_ui()
        self.refresh_all_lists()
        self._bind_shortcuts()

    def _apply_role_permissions(self):
        role = (self.user_info.get("role") or "").lower()
        if role == "operador":
            # Disable admin-only tabs
            try:
                self.nb_main.tab(self.tab_cat, state="disabled")
                self.nb_main.tab(self.tab_cfg, state="disabled")
                self.nb_main.tab(self.tab_users, state="disabled")
            except Exception:
                pass
            # Disable destructive actions
            for btn in (
                getattr(self, "btn_cargas_delete", None),
                getattr(self, "btn_cargas_edit", None),
                getattr(self, "btn_cargas_csv", None),
                getattr(self, "btn_cargas_excel", None),
            ):
                if btn:
                    btn.state(["disabled"])
            if getattr(self, "btn_update_carga", None):
                self.btn_update_carga.state(["disabled"])
            # Disable edit in orders, keep print/pdf
            if getattr(self, "btn_orden_edit", None):
                self.btn_orden_edit.state(["disabled"])

    def open_calendar(self, entry):
        if Calendar is None:
            messagebox.showerror("Error", "Falta tkcalendar. Instala: pip install tkcalendar")
            return
        win = tk.Toplevel(self)
        win.title("Seleccionar fecha")
        win.geometry("300x260")
        cal = Calendar(win, selectmode="day", date_pattern="yyyy-mm-dd")
        cal.pack(padx=10, pady=10, fill="both", expand=True)

        def select_date():
            entry.delete(0, tk.END)
            entry.insert(0, cal.get_date())
            win.destroy()

        ttk.Button(win, text="Seleccionar", command=select_date).pack(pady=6)

    def _date_field(self, parent, width):
        frame = ttk.Frame(parent)
        entry = ttk.Entry(frame, width=width)
        entry.pack(side="left")
        ttk.Button(frame, text="Cal", command=lambda e=entry: self.open_calendar(e)).pack(
            side="left", padx=4
        )
        return frame, entry

    def _set_icon(self):
        ico = resource_path("camion-de-carga.ico")
        png = resource_path("camion-de-carga.png")
        try:
            if os.path.exists(png):
                img = tk.PhotoImage(file=png)
                self.iconphoto(True, img)
                self._icon_ref = img
            if os.path.exists(ico):
                try:
                    self.iconbitmap(ico)
                except Exception:
                    pass
        except Exception:
            pass

    def _build_ui(self):
        root = tk.Frame(self, bg=COLOR_BG)
        root.pack(fill="both", expand=True)

        header = tk.Frame(root, bg=COLOR_ACCENT, height=50)
        header.pack(fill="x", pady=(0, 10))
        header.pack_propagate(False)

        title = tk.Label(
            header, text=APP_NAME, bg=COLOR_ACCENT, fg="white", font=("Helvetica", 16, "bold")
        )
        title.pack(side="left", padx=12, pady=10)

        self.nb_main = ttk.Notebook(root)
        self.nb_main.pack(fill="both", expand=True, padx=8)

        self.tab_reg = ttk.Frame(self.nb_main, padding=10)
        self.tab_stats = ttk.Frame(self.nb_main, padding=10)
        self.tab_cat = ttk.Frame(self.nb_main, padding=10)
        self.tab_cfg = ttk.Frame(self.nb_main, padding=10)
        self.tab_ordenes = ttk.Frame(self.nb_main, padding=10)
        self.tab_users = ttk.Frame(self.nb_main, padding=10)
        self.nb_main.add(self.tab_reg, text="Registro")
        self.nb_main.add(self.tab_stats, text="Estadísticas")
        self.nb_main.add(self.tab_ordenes, text="Órdenes")
        self.nb_main.add(self.tab_cat, text="Catálogos")
        self.nb_main.add(self.tab_cfg, text="Configuración")
        self.nb_main.add(self.tab_users, text="Usuarios")

        self._build_registro()
        self._build_stats()
        self._build_ordenes()
        self._build_catalogos()
        self._build_config()
        self._build_users()
        self._apply_role_permissions()

        footer = tk.Frame(root, bg=COLOR_DARK, height=26)
        footer.pack(fill="x", pady=(8, 0))
        footer.pack_propagate(False)
        display_name = self.user_info.get("nombre") or self.user_info.get("username")
        tk.Label(
            footer,
            text=f"Sesión iniciada por: {display_name} | Rol: {self.user_info.get('role')}",
            bg=COLOR_DARK,
            fg="white",
            font=("Helvetica", 10),
        ).pack(side="left", padx=10, pady=4)
        tk.Label(
            footer,
            text="Desarrollado por Ing Leonardo Sanchez - 2026",
            bg=COLOR_DARK,
            fg=COLOR_HI,
            font=("Helvetica", 10, "bold"),
        ).pack(side="right", padx=10, pady=4)

    def _bind_shortcuts(self):
        self.bind_all("<Control-s>", lambda _e: self.on_save())
        self.bind_all("<Control-Shift-S>", lambda _e: self.on_update_carga())
        self.bind_all("<Delete>", lambda _e: self.on_delete_carga())
        self.bind_all("<Escape>", lambda _e: self.clear_ordenes_filters())

    def _build_registro(self):
        frm = self.tab_reg

        fields = [
            ("Vehículo (placa)", "vehiculo"),
            ("Conductor (cédula/nombre)", "conductor"),
            ("Tipo de carga", "tipo"),
            ("Fecha carga (YYYY-MM-DD)", "fcarga"),
            ("Fecha descarga (YYYY-MM-DD)", "fdesc"),
            ("Origen (ciudad)", "origen"),
            ("Destino (ciudad)", "destino"),
            ("Bodega origen (opcional)", "bodega_origen"),
            ("Bodega destino (opcional)", "bodega_destino"),
            ("Peso (kg)", "peso"),
        ]

        self.inputs = {}

        left = ttk.Frame(frm)
        left.pack(side="left", fill="y")
        right = ttk.Frame(frm)
        right.pack(side="left", padx=20, fill="both", expand=True)

        for i, (label, key) in enumerate(fields):
            ttk.Label(left, text=label).grid(row=i, column=0, sticky="w", pady=4)
            if key in ("vehiculo", "conductor", "tipo", "origen", "destino", "bodega_origen", "bodega_destino"):
                cb = ttk.Combobox(left, width=34, values=[])
                cb.grid(row=i, column=1, pady=4)
                ttk.Button(left, text="Buscar", command=lambda k=key: self.open_search(k)).grid(
                    row=i, column=2, padx=6
                )
                self.inputs[key] = cb
            elif key in ("fcarga", "fdesc"):
                df, entry = self._date_field(left, 30)
                df.grid(row=i, column=1, pady=4, sticky="w")
                self.inputs[key] = entry
            else:
                e = ttk.Entry(left, width=36)
                e.grid(row=i, column=1, pady=4)
                self.inputs[key] = e

        actions = ttk.Frame(left)
        actions.grid(row=len(fields), column=0, columnspan=3, pady=(8, 0), sticky="w")
        ttk.Button(actions, text="Guardar", command=self.on_save).pack(side="left", padx=(0, 8))
        self.btn_update_carga = ttk.Button(actions, text="Actualizar carga", command=self.on_update_carga)
        self.btn_update_carga.pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(actions, text="Limpiar", command=self.on_clear).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Actualizar listas", command=self.refresh_all_lists).pack(
            side="left"
        )

        self.lbl_carga_sel = ttk.Label(left, text="Carga seleccionada: ninguna")
        self.lbl_carga_sel.grid(row=len(fields) + 1, column=0, columnspan=3, sticky="w", pady=(6, 0))

        info = (
            "Consejos:\n"
            "- Crea conductores, vehículos, tipos, ciudades y bodegas en la pestaña Catálogos.\n"
            "- Usa fechas en formato YYYY-MM-DD.\n"
            "- El peso debe ser numérico."
        )
        ttk.Label(right, text=info, justify="left").pack(anchor="nw")

    def _build_stats(self):
        frm = self.tab_stats

        filters = ttk.LabelFrame(frm, text="Filtros", padding=10)
        filters.pack(fill="x")

        ttk.Label(filters, text="Vehículo (placa)").grid(row=0, column=0, sticky="w")
        self.f_vehiculo = ttk.Combobox(filters, width=16, values=[])
        self.f_vehiculo.grid(row=0, column=1, padx=6)

        ttk.Label(filters, text="Tipo carga").grid(row=0, column=2, sticky="w")
        self.f_tipo = ttk.Combobox(filters, width=20, values=[])
        self.f_tipo.grid(row=0, column=3, padx=6)

        ttk.Label(filters, text="Fecha inicio").grid(row=1, column=0, sticky="w")
        f_ini_frame, self.f_ini = self._date_field(filters, 12)
        f_ini_frame.grid(row=1, column=1, padx=6, sticky="w")

        ttk.Label(filters, text="Fecha fin").grid(row=1, column=2, sticky="w")
        f_fin_frame, self.f_fin = self._date_field(filters, 12)
        f_fin_frame.grid(row=1, column=3, padx=6, sticky="w")

        ttk.Button(filters, text="Calcular", command=self.on_stats).grid(
            row=0, column=4, rowspan=2, padx=10
        )

        summary = ttk.LabelFrame(frm, text="Resumen", padding=10)
        summary.pack(fill="x", pady=(10, 0))

        self.lbl_total = ttk.Label(summary, text="Registros: 0")
        self.lbl_total.pack(side="left", padx=(0, 20))
        self.lbl_kg = ttk.Label(summary, text="Total kg: 0")
        self.lbl_kg.pack(side="left", padx=(0, 20))
        self.lbl_avg = ttk.Label(summary, text="Promedio kg: 0")
        self.lbl_avg.pack(side="left", padx=(0, 20))
        self.lbl_maxmin = ttk.Label(summary, text="Max/Min: 0 / 0")
        self.lbl_maxmin.pack(side="left")

        out = ttk.LabelFrame(frm, text="Detalle", padding=10)
        out.pack(fill="both", expand=True, pady=(10, 0))

        self.txt = tk.Text(out, width=110, height=22)
        self.txt.pack(fill="both", expand=True)

        alert = ttk.LabelFrame(frm, text="Panel de alerta (según fecha de descarga)", padding=10)
        alert.pack(fill="both", expand=False, pady=(10, 0))

        self.alert_list = tk.Listbox(alert, height=8, width=110)
        self.alert_list.pack(side="left", fill="both", expand=True)

        btns = ttk.Frame(alert)
        btns.pack(side="right", fill="y", padx=6)
        ttk.Button(btns, text="Actualizar", command=self.refresh_alertas).pack(pady=4)
        ttk.Label(
            btns,
            text="Regla:\n- fecha_descarga > hoy = ENTREGADO\n- fecha_descarga < hoy = PENDIENTE",
            justify="left",
        ).pack(pady=6)

        cargas = ttk.LabelFrame(frm, text="Cargas (CRUD)", padding=10)
        cargas.pack(fill="both", expand=False, pady=(10, 0))

        c_top = ttk.Frame(cargas)
        c_top.pack(fill="x", pady=(0, 6))
        ttk.Label(c_top, text="Buscar").pack(side="left")
        self.cargas_search = ttk.Entry(c_top, width=30)
        self.cargas_search.pack(side="left", padx=6)
        self.cargas_search.bind("<KeyRelease>", lambda _e: self.refresh_cargas())
        ttk.Button(c_top, text="Limpiar", command=self.clear_cargas_search).pack(side="left")

        self.cargas_list = tk.Listbox(cargas, height=8, width=110)
        self.cargas_list.pack(side="left", fill="both", expand=True)

        cbtns = ttk.Frame(cargas)
        cbtns.pack(side="right", fill="y", padx=6)
        self.btn_cargas_refresh = ttk.Button(cbtns, text="Actualizar", command=self.refresh_cargas)
        self.btn_cargas_refresh.pack(pady=4)
        self.btn_cargas_edit = ttk.Button(cbtns, text="Editar", command=self.on_edit_carga)
        self.btn_cargas_edit.pack(pady=4)
        self.btn_cargas_delete = ttk.Button(cbtns, text="Eliminar", command=self.on_delete_carga)
        self.btn_cargas_delete.pack(pady=4)
        self.btn_cargas_print = ttk.Button(cbtns, text="Imprimir", command=self.on_print_carga)
        self.btn_cargas_print.pack(pady=4)
        self.btn_cargas_pdf = ttk.Button(cbtns, text="PDF", command=self.on_pdf_carga)
        self.btn_cargas_pdf.pack(pady=4)
        self.btn_cargas_csv = ttk.Button(cbtns, text="Exportar CSV", command=self.export_cargas_csv)
        self.btn_cargas_csv.pack(pady=4)
        self.btn_cargas_excel = ttk.Button(cbtns, text="Exportar Excel", command=self.export_cargas_excel)
        self.btn_cargas_excel.pack(pady=4)

    def _build_catalogos(self):
        frm = self.tab_cat
        nb = ttk.Notebook(frm)
        nb.pack(fill="both", expand=True)

        self.tab_conductores = ttk.Frame(nb, padding=10)
        self.tab_vehiculos = ttk.Frame(nb, padding=10)
        self.tab_tipos = ttk.Frame(nb, padding=10)
        self.tab_ciudades = ttk.Frame(nb, padding=10)
        self.tab_bodegas = ttk.Frame(nb, padding=10)

        nb.add(self.tab_conductores, text="Conductores")
        nb.add(self.tab_vehiculos, text="Vehículos")
        nb.add(self.tab_tipos, text="Tipos de carga")
        nb.add(self.tab_ciudades, text="Ciudades")
        nb.add(self.tab_bodegas, text="Bodegas")

        self._build_cat_conductores()
        self._build_cat_vehiculos()
        self._build_cat_tipos()
        self._build_cat_ciudades()
        self._build_cat_bodegas()

    def _build_users(self):
        frm = self.tab_users
        ttk.Label(frm, text="Usuario").grid(row=0, column=0, sticky="w")
        self.u_username = ttk.Entry(frm, width=24)
        self.u_username.grid(row=0, column=1, padx=6)

        ttk.Label(frm, text="Nombre").grid(row=0, column=2, sticky="w")
        self.u_nombre = ttk.Entry(frm, width=24)
        self.u_nombre.grid(row=0, column=3, padx=6)

        ttk.Label(frm, text="Cédula").grid(row=0, column=4, sticky="w")
        self.u_cedula = ttk.Entry(frm, width=18)
        self.u_cedula.grid(row=0, column=5, padx=6)

        ttk.Label(frm, text="Rol").grid(row=1, column=0, sticky="w")
        self.u_role = ttk.Combobox(frm, width=22, values=["administrador", "operador"])
        self.u_role.grid(row=1, column=1, padx=6)

        ttk.Label(frm, text="Contraseña").grid(row=1, column=2, sticky="w")
        self.u_password = ttk.Entry(frm, width=24, show="*")
        self.u_password.grid(row=1, column=3, padx=6)

        self.u_active = tk.IntVar(value=1)
        ttk.Checkbutton(frm, text="Activo", variable=self.u_active).grid(row=1, column=4, sticky="w")

        ubtns = ttk.Frame(frm)
        ubtns.grid(row=0, column=6, rowspan=2, padx=6, sticky="ns")
        ttk.Button(ubtns, text="Crear", command=self.on_create_user).pack(fill="x", pady=2)
        ttk.Button(ubtns, text="Actualizar", command=self.on_update_user).pack(fill="x", pady=2)
        ttk.Button(ubtns, text="Desactivar", command=self.on_deactivate_user).pack(fill="x", pady=2)
        ttk.Button(ubtns, text="Reactivar", command=self.on_reactivate_user).pack(fill="x", pady=2)

        ttk.Label(frm, text="Buscar").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.u_search = ttk.Entry(frm, width=24)
        self.u_search.grid(row=2, column=1, padx=6, pady=(6, 0))
        self.u_search.bind("<KeyRelease>", lambda _e: self.refresh_users())
        ttk.Button(frm, text="Limpiar", command=self.clear_users_form).grid(
            row=2, column=2, padx=6, pady=(6, 0)
        )

        self.u_list = tk.Listbox(frm, height=14, width=90)
        self.u_list.grid(row=3, column=0, columnspan=7, pady=10, sticky="w")
        self.u_list.bind("<<ListboxSelect>>", self.on_select_user)

    def _build_ordenes(self):
        frm = self.tab_ordenes

        filtros = ttk.LabelFrame(frm, text="Buscar órdenes", padding=10)
        filtros.pack(fill="x")

        ttk.Label(filtros, text="Buscar").grid(row=0, column=0, sticky="w")
        self.o_search = ttk.Entry(filtros, width=30)
        self.o_search.grid(row=0, column=1, padx=6)
        self.o_search.bind("<KeyRelease>", lambda _e: self.refresh_ordenes())
        ttk.Button(filtros, text="Borrar búsqueda", command=self.clear_ordenes_filters).grid(
            row=0, column=2, padx=6
        )

        ttk.Label(filtros, text="Vehículo (placa)").grid(row=0, column=3, sticky="w")
        self.o_vehiculo = ttk.Combobox(filtros, width=16, values=[])
        self.o_vehiculo.grid(row=0, column=4, padx=6)
        self.o_vehiculo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_ordenes())

        ttk.Label(filtros, text="Tipo carga").grid(row=0, column=5, sticky="w")
        self.o_tipo = ttk.Combobox(filtros, width=18, values=[])
        self.o_tipo.grid(row=0, column=6, padx=6)
        self.o_tipo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_ordenes())

        ttk.Label(filtros, text="Fecha inicio").grid(row=1, column=0, sticky="w")
        o_ini_frame, self.o_ini = self._date_field(filtros, 12)
        o_ini_frame.grid(row=1, column=1, padx=6, sticky="w")

        ttk.Label(filtros, text="Fecha fin").grid(row=1, column=2, sticky="w")
        o_fin_frame, self.o_fin = self._date_field(filtros, 12)
        o_fin_frame.grid(row=1, column=3, padx=6, sticky="w")

        ttk.Button(filtros, text="Actualizar", command=self.refresh_ordenes).grid(
            row=0, column=7, rowspan=2, padx=8
        )
        ttk.Button(filtros, text="Limpiar", command=self.clear_ordenes_filters).grid(
            row=0, column=8, rowspan=2, padx=8
        )
        self.o_msg = ttk.Label(filtros, text="Usa un filtro o búsqueda para ver resultados.")
        self.o_msg.grid(row=2, column=0, columnspan=9, sticky="w", pady=(6, 0))

        lista = ttk.LabelFrame(frm, text="Órdenes encontradas", padding=10)
        lista.pack(fill="both", expand=True, pady=(10, 0))

        self.o_list = tk.Listbox(lista, height=14, width=110)
        self.o_list.pack(side="left", fill="both", expand=True)
        self.o_list.bind("<<ListboxSelect>>", self.on_select_orden)
        self.o_list.bind("<Double-1>", lambda _e: self.on_print_orden())

        det = ttk.LabelFrame(frm, text="Detalle de la orden", padding=10)
        det.pack(fill="both", expand=True, pady=(10, 0))

        obtns = ttk.Frame(det)
        obtns.pack(fill="x", pady=(0, 8))
        self.btn_orden_edit = ttk.Button(obtns, text="Editar", command=self.on_edit_orden)
        self.btn_orden_edit.pack(side="left", padx=6)
        self.btn_orden_print = ttk.Button(obtns, text="Imprimir", command=self.on_print_orden)
        self.btn_orden_print.pack(side="left", padx=6)
        self.btn_orden_pdf = ttk.Button(obtns, text="PDF", command=self.on_pdf_orden)
        self.btn_orden_pdf.pack(side="left", padx=6)

        self.o_det = tk.Text(det, width=110, height=10)
        self.o_det.pack(fill="both", expand=True)

    def _build_config(self):
        frm = self.tab_cfg
        ttk.Label(frm, text="Encabezado del recibo").grid(row=0, column=0, sticky="w")
        self.cfg_header = ttk.Entry(frm, width=60)
        self.cfg_header.grid(row=0, column=1, padx=6, pady=4, sticky="w")

        ttk.Label(frm, text="NIT").grid(row=1, column=0, sticky="w")
        self.cfg_nit = ttk.Entry(frm, width=40)
        self.cfg_nit.grid(row=1, column=1, padx=6, pady=4, sticky="w")

        ttk.Label(frm, text="Dirección").grid(row=2, column=0, sticky="w")
        self.cfg_dir = ttk.Entry(frm, width=60)
        self.cfg_dir.grid(row=2, column=1, padx=6, pady=4, sticky="w")

        ttk.Label(frm, text="Teléfono").grid(row=3, column=0, sticky="w")
        self.cfg_tel = ttk.Entry(frm, width=40)
        self.cfg_tel.grid(row=3, column=1, padx=6, pady=4, sticky="w")

        ttk.Label(frm, text="Logo (PNG)").grid(row=4, column=0, sticky="w")
        self.cfg_logo = ttk.Entry(frm, width=60)
        self.cfg_logo.grid(row=4, column=1, padx=6, pady=4, sticky="w")
        ttk.Button(frm, text="Buscar", command=self.on_browse_logo).grid(
            row=4, column=2, padx=6, pady=4
        )

        self.cfg_logo_preview = ttk.Label(frm, text="Sin logo")
        self.cfg_logo_preview.grid(row=5, column=1, sticky="w", padx=6, pady=6)

        ttk.Button(frm, text="Guardar configuración", command=self.on_save_config).grid(
            row=6, column=1, sticky="w", padx=6, pady=8
        )

    def _build_cat_conductores(self):
        frm = self.tab_conductores
        ttk.Label(frm, text="Nombre").grid(row=0, column=0, sticky="w")
        self.c_nombre = ttk.Entry(frm, width=30)
        self.c_nombre.grid(row=0, column=1, padx=6)

        ttk.Label(frm, text="Cédula").grid(row=0, column=2, sticky="w")
        self.c_cedula = ttk.Entry(frm, width=20)
        self.c_cedula.grid(row=0, column=3, padx=6)

        cbtns = ttk.Frame(frm)
        cbtns.grid(row=0, column=4, rowspan=2, padx=6, sticky="ns")
        ttk.Button(cbtns, text="Guardar", command=self.on_add_conductor).pack(fill="x", pady=2)
        ttk.Button(cbtns, text="Actualizar", command=self.on_update_conductor).pack(fill="x", pady=2)
        ttk.Button(cbtns, text="Eliminar", command=self.on_delete_conductor).pack(fill="x", pady=2)

        ttk.Label(frm, text="Buscar").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.c_search = ttk.Entry(frm, width=30)
        self.c_search.grid(row=1, column=1, padx=6, pady=(6, 0))
        self.c_search.bind("<KeyRelease>", lambda _e: self._refresh_catalog_lists())
        ttk.Button(frm, text="Limpiar selección", command=self.clear_conductor_selection).grid(
            row=1, column=2, padx=6, pady=(6, 0)
        )

        self.c_list = tk.Listbox(frm, height=16, width=70)
        self.c_list.grid(row=2, column=0, columnspan=5, pady=10, sticky="w")
        self.c_list.bind("<<ListboxSelect>>", self.on_select_conductor)

    def _build_cat_vehiculos(self):
        frm = self.tab_vehiculos
        ttk.Label(frm, text="Placa").grid(row=0, column=0, sticky="w")
        self.v_placa = ttk.Entry(frm, width=30)
        self.v_placa.grid(row=0, column=1, padx=6)
        vbtns = ttk.Frame(frm)
        vbtns.grid(row=0, column=2, rowspan=2, padx=6, sticky="ns")
        ttk.Button(vbtns, text="Guardar", command=self.on_add_vehiculo).pack(fill="x", pady=2)
        ttk.Button(vbtns, text="Actualizar", command=self.on_update_vehiculo).pack(fill="x", pady=2)
        ttk.Button(vbtns, text="Eliminar", command=self.on_delete_vehiculo).pack(fill="x", pady=2)

        ttk.Label(frm, text="Buscar").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.v_search = ttk.Entry(frm, width=30)
        self.v_search.grid(row=1, column=1, padx=6, pady=(6, 0))
        self.v_search.bind("<KeyRelease>", lambda _e: self._refresh_catalog_lists())
        ttk.Button(frm, text="Limpiar selección", command=self.clear_vehiculo_selection).grid(
            row=1, column=3, padx=6, pady=(6, 0)
        )

        self.v_list = tk.Listbox(frm, height=16, width=70)
        self.v_list.grid(row=2, column=0, columnspan=3, pady=10, sticky="w")
        self.v_list.bind("<<ListboxSelect>>", self.on_select_vehiculo)

    def _build_cat_tipos(self):
        frm = self.tab_tipos
        ttk.Label(frm, text="Nombre").grid(row=0, column=0, sticky="w")
        self.t_nombre = ttk.Entry(frm, width=30)
        self.t_nombre.grid(row=0, column=1, padx=6)
        tbtns = ttk.Frame(frm)
        tbtns.grid(row=0, column=2, rowspan=2, padx=6, sticky="ns")
        ttk.Button(tbtns, text="Guardar", command=self.on_add_tipo).pack(fill="x", pady=2)
        ttk.Button(tbtns, text="Actualizar", command=self.on_update_tipo).pack(fill="x", pady=2)
        ttk.Button(tbtns, text="Eliminar", command=self.on_delete_tipo).pack(fill="x", pady=2)

        ttk.Label(frm, text="Buscar").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.t_search = ttk.Entry(frm, width=30)
        self.t_search.grid(row=1, column=1, padx=6, pady=(6, 0))
        self.t_search.bind("<KeyRelease>", lambda _e: self._refresh_catalog_lists())
        ttk.Button(frm, text="Limpiar selección", command=self.clear_tipo_selection).grid(
            row=1, column=3, padx=6, pady=(6, 0)
        )

        self.t_list = tk.Listbox(frm, height=16, width=70)
        self.t_list.grid(row=2, column=0, columnspan=3, pady=10, sticky="w")
        self.t_list.bind("<<ListboxSelect>>", self.on_select_tipo)

    def _build_cat_ciudades(self):
        frm = self.tab_ciudades
        ttk.Label(frm, text="Nombre").grid(row=0, column=0, sticky="w")
        self.ci_nombre = ttk.Entry(frm, width=30)
        self.ci_nombre.grid(row=0, column=1, padx=6)
        cibtns = ttk.Frame(frm)
        cibtns.grid(row=0, column=2, rowspan=2, padx=6, sticky="ns")
        ttk.Button(cibtns, text="Guardar", command=self.on_add_ciudad).pack(fill="x", pady=2)
        ttk.Button(cibtns, text="Actualizar", command=self.on_update_ciudad).pack(fill="x", pady=2)
        ttk.Button(cibtns, text="Eliminar", command=self.on_delete_ciudad).pack(fill="x", pady=2)

        ttk.Label(frm, text="Buscar").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.ci_search = ttk.Entry(frm, width=30)
        self.ci_search.grid(row=1, column=1, padx=6, pady=(6, 0))
        self.ci_search.bind("<KeyRelease>", lambda _e: self._refresh_catalog_lists())
        ttk.Button(frm, text="Limpiar selección", command=self.clear_ciudad_selection).grid(
            row=1, column=3, padx=6, pady=(6, 0)
        )

        self.ci_list = tk.Listbox(frm, height=16, width=70)
        self.ci_list.grid(row=2, column=0, columnspan=3, pady=10, sticky="w")
        self.ci_list.bind("<<ListboxSelect>>", self.on_select_ciudad)

    def _build_cat_bodegas(self):
        frm = self.tab_bodegas
        ttk.Label(frm, text="Nombre").grid(row=0, column=0, sticky="w")
        self.b_nombre = ttk.Entry(frm, width=30)
        self.b_nombre.grid(row=0, column=1, padx=6)

        ttk.Label(frm, text="Ciudad").grid(row=0, column=2, sticky="w")
        self.b_ciudad = ttk.Combobox(frm, width=20, values=[])
        self.b_ciudad.grid(row=0, column=3, padx=6)

        bbtns = ttk.Frame(frm)
        bbtns.grid(row=0, column=4, rowspan=2, padx=6, sticky="ns")
        ttk.Button(bbtns, text="Guardar", command=self.on_add_bodega).pack(fill="x", pady=2)
        ttk.Button(bbtns, text="Actualizar", command=self.on_update_bodega).pack(fill="x", pady=2)
        ttk.Button(bbtns, text="Eliminar", command=self.on_delete_bodega).pack(fill="x", pady=2)

        ttk.Label(frm, text="Buscar").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.b_search = ttk.Entry(frm, width=30)
        self.b_search.grid(row=1, column=1, padx=6, pady=(6, 0))
        self.b_search.bind("<KeyRelease>", lambda _e: self._refresh_catalog_lists())
        ttk.Button(frm, text="Limpiar selección", command=self.clear_bodega_selection).grid(
            row=1, column=2, padx=6, pady=(6, 0)
        )

        self.b_list = tk.Listbox(frm, height=16, width=70)
        self.b_list.grid(row=2, column=0, columnspan=5, pady=10, sticky="w")
        self.b_list.bind("<<ListboxSelect>>", self.on_select_bodega)

    # ---- List refresh ----
    def refresh_all_lists(self):
        self.conductores = list_conductores()
        self.vehiculos = list_vehiculos()
        self.tipos = list_tipos()
        self.ciudades = list_ciudades()
        self.bodegas = list_bodegas()

        self.conductores_by_id = {cid: (cid, nombre, cedula) for cid, nombre, cedula in self.conductores}
        self.vehiculos_by_id = {vid: (vid, placa) for vid, placa in self.vehiculos}
        self.tipos_by_id = {tid: (tid, nombre) for tid, nombre in self.tipos}
        self.ciudades_by_id = {cid: (cid, nombre) for cid, nombre in self.ciudades}
        self.bodegas_by_id = {bid: (bid, nombre, ciudad) for bid, nombre, ciudad in self.bodegas}

        self.map_conductores = {}
        c_labels = []
        for cid, nombre, cedula in self.conductores:
            label = f"{cedula} - {nombre}" if cedula else nombre
            self.map_conductores[label] = cid
            c_labels.append(label)

        self.map_vehiculos = {}
        v_labels = []
        for vid, placa in self.vehiculos:
            self.map_vehiculos[placa] = vid
            v_labels.append(placa)

        self.map_tipos = {}
        t_labels = []
        for tid, nombre in self.tipos:
            self.map_tipos[nombre] = tid
            t_labels.append(nombre)

        self.map_ciudades = {}
        ci_labels = []
        for cid, nombre in self.ciudades:
            self.map_ciudades[nombre] = cid
            ci_labels.append(nombre)

        self.map_bodegas = {}
        b_labels = []
        for bid, nombre, ciudad in self.bodegas:
            label = f"{nombre} ({ciudad})" if ciudad else nombre
            self.map_bodegas[label] = bid
            b_labels.append(label)

        for key in ("conductor",):
            self.inputs[key]["values"] = c_labels
        for key in ("vehiculo",):
            self.inputs[key]["values"] = v_labels
        for key in ("tipo",):
            self.inputs[key]["values"] = t_labels
        for key in ("origen", "destino"):
            self.inputs[key]["values"] = ci_labels
        for key in ("bodega_origen", "bodega_destino"):
            self.inputs[key]["values"] = b_labels

        self.f_vehiculo["values"] = v_labels
        self.f_tipo["values"] = t_labels
        self.b_ciudad["values"] = ci_labels
        self.o_vehiculo["values"] = v_labels
        self.o_tipo["values"] = t_labels

        self._refresh_catalog_lists()
        self.refresh_alertas()
        self.refresh_cargas()
        self.refresh_ordenes()
        self.refresh_users()
        self.load_config()

    def _refresh_catalog_lists(self):
        self.c_index = []
        self.v_index = []
        self.t_index = []
        self.ci_index = []
        self.b_index = []

        c_term = self.c_search.get().strip().lower() if hasattr(self, "c_search") else ""
        v_term = self.v_search.get().strip().lower() if hasattr(self, "v_search") else ""
        t_term = self.t_search.get().strip().lower() if hasattr(self, "t_search") else ""
        ci_term = self.ci_search.get().strip().lower() if hasattr(self, "ci_search") else ""
        b_term = self.b_search.get().strip().lower() if hasattr(self, "b_search") else ""

        self.c_list.delete(0, tk.END)
        for _id, nombre, cedula in self.conductores:
            label = f"{cedula} - {nombre}" if cedula else nombre
            if c_term and c_term not in label.lower():
                continue
            self.c_list.insert(tk.END, label)
            self.c_index.append(_id)

        self.v_list.delete(0, tk.END)
        for _id, placa in self.vehiculos:
            if v_term and v_term not in placa.lower():
                continue
            self.v_list.insert(tk.END, placa)
            self.v_index.append(_id)

        self.t_list.delete(0, tk.END)
        for _id, nombre in self.tipos:
            if t_term and t_term not in nombre.lower():
                continue
            self.t_list.insert(tk.END, nombre)
            self.t_index.append(_id)

        self.ci_list.delete(0, tk.END)
        for _id, nombre in self.ciudades:
            if ci_term and ci_term not in nombre.lower():
                continue
            self.ci_list.insert(tk.END, nombre)
            self.ci_index.append(_id)

        self.b_list.delete(0, tk.END)
        for _id, nombre, ciudad in self.bodegas:
            label = f"{nombre} ({ciudad})" if ciudad else nombre
            if b_term and b_term not in label.lower():
                continue
            self.b_list.insert(tk.END, label)
            self.b_index.append(_id)

    # ---- Search ----
    def open_search(self, key):
        if key == "conductor":
            items = [(i, l) for l, i in self.map_conductores.items()]
            title = "Buscar conductor"
        elif key == "vehiculo":
            items = [(i, l) for l, i in self.map_vehiculos.items()]
            title = "Buscar vehículo"
        elif key == "tipo":
            items = [(i, l) for l, i in self.map_tipos.items()]
            title = "Buscar tipo"
        elif key in ("origen", "destino"):
            items = [(i, l) for l, i in self.map_ciudades.items()]
            title = "Buscar ciudad"
        else:
            items = [(i, l) for l, i in self.map_bodegas.items()]
            title = "Buscar bodega"

        dlg = SearchDialog(self, items, title=title)
        self.wait_window(dlg)
        if dlg.selected:
            self.inputs[key].set(dlg.selected)

    # ---- Catalog actions ----
    def on_add_conductor(self):
        try:
            nombre = self.c_nombre.get().strip()
            cedula = self.c_cedula.get().strip()
            if not nombre:
                raise ValueError("Nombre requerido")
            add_conductor(nombre, cedula)
            self.c_nombre.delete(0, tk.END)
            self.c_cedula.delete(0, tk.END)
            self.refresh_all_lists()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_select_conductor(self, _event=None):
        idx = self.c_list.curselection()
        if not idx:
            return
        i = idx[0]
        if i >= len(self.c_index):
            return
        _id = self.c_index[i]
        _id, nombre, cedula = self.conductores_by_id.get(_id, (_id, "", ""))
        self.c_selected = _id
        self.c_nombre.delete(0, tk.END)
        self.c_nombre.insert(0, nombre)
        self.c_cedula.delete(0, tk.END)
        if cedula:
            self.c_cedula.insert(0, cedula)

    def on_update_conductor(self):
        try:
            cid = getattr(self, "c_selected", None)
            if not cid:
                raise ValueError("Selecciona un conductor de la lista")
            nombre = self.c_nombre.get().strip()
            cedula = self.c_cedula.get().strip()
            if not nombre:
                raise ValueError("Nombre requerido")
            update_conductor(cid, nombre, cedula)
            self.refresh_all_lists()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def clear_conductor_selection(self):
        self.c_list.selection_clear(0, tk.END)
        self.c_selected = None
        self.c_nombre.delete(0, tk.END)
        self.c_cedula.delete(0, tk.END)

    def on_delete_conductor(self):
        try:
            cid = getattr(self, "c_selected", None)
            if not cid:
                raise ValueError("Selecciona un conductor de la lista")
            if not messagebox.askyesno("Confirmar", "¿Eliminar conductor seleccionado?"):
                return
            delete_conductor(cid)
            self.c_selected = None
            self.refresh_all_lists()
        except sqlite3.IntegrityError:
            messagebox.showerror(
                "Error",
                "No se puede eliminar: hay cargas asociadas a este conductor.",
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_add_vehiculo(self):
        try:
            placa = self.v_placa.get().strip().upper()
            if not placa:
                raise ValueError("Placa requerida")
            add_vehiculo(placa)
            self.v_placa.delete(0, tk.END)
            self.refresh_all_lists()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_select_vehiculo(self, _event=None):
        idx = self.v_list.curselection()
        if not idx:
            return
        i = idx[0]
        if i >= len(self.v_index):
            return
        _id = self.v_index[i]
        _id, placa = self.vehiculos_by_id.get(_id, (_id, ""))
        self.v_selected = _id
        self.v_placa.delete(0, tk.END)
        self.v_placa.insert(0, placa)

    def on_update_vehiculo(self):
        try:
            vid = getattr(self, "v_selected", None)
            if not vid:
                raise ValueError("Selecciona un vehículo de la lista")
            placa = self.v_placa.get().strip().upper()
            if not placa:
                raise ValueError("Placa requerida")
            update_vehiculo(vid, placa)
            self.refresh_all_lists()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def clear_vehiculo_selection(self):
        self.v_list.selection_clear(0, tk.END)
        self.v_selected = None
        self.v_placa.delete(0, tk.END)

    def on_delete_vehiculo(self):
        try:
            vid = getattr(self, "v_selected", None)
            if not vid:
                raise ValueError("Selecciona un vehículo de la lista")
            if not messagebox.askyesno("Confirmar", "¿Eliminar vehículo seleccionado?"):
                return
            delete_vehiculo(vid)
            self.v_selected = None
            self.refresh_all_lists()
        except sqlite3.IntegrityError:
            messagebox.showerror(
                "Error",
                "No se puede eliminar: hay cargas asociadas a este vehículo.",
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_add_tipo(self):
        try:
            nombre = self.t_nombre.get().strip()
            if not nombre:
                raise ValueError("Nombre requerido")
            add_tipo(nombre)
            self.t_nombre.delete(0, tk.END)
            self.refresh_all_lists()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_select_tipo(self, _event=None):
        idx = self.t_list.curselection()
        if not idx:
            return
        i = idx[0]
        if i >= len(self.t_index):
            return
        _id = self.t_index[i]
        _id, nombre = self.tipos_by_id.get(_id, (_id, ""))
        self.t_selected = _id
        self.t_nombre.delete(0, tk.END)
        self.t_nombre.insert(0, nombre)

    def on_update_tipo(self):
        try:
            tid = getattr(self, "t_selected", None)
            if not tid:
                raise ValueError("Selecciona un tipo de carga de la lista")
            nombre = self.t_nombre.get().strip()
            if not nombre:
                raise ValueError("Nombre requerido")
            update_tipo(tid, nombre)
            self.refresh_all_lists()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def clear_tipo_selection(self):
        self.t_list.selection_clear(0, tk.END)
        self.t_selected = None
        self.t_nombre.delete(0, tk.END)

    def on_delete_tipo(self):
        try:
            tid = getattr(self, "t_selected", None)
            if not tid:
                raise ValueError("Selecciona un tipo de carga de la lista")
            if not messagebox.askyesno("Confirmar", "¿Eliminar tipo de carga seleccionado?"):
                return
            delete_tipo(tid)
            self.t_selected = None
            self.refresh_all_lists()
        except sqlite3.IntegrityError:
            messagebox.showerror(
                "Error",
                "No se puede eliminar: hay cargas asociadas a este tipo de carga.",
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_add_ciudad(self):
        try:
            nombre = self.ci_nombre.get().strip()
            if not nombre:
                raise ValueError("Nombre requerido")
            add_ciudad(nombre)
            self.ci_nombre.delete(0, tk.END)
            self.refresh_all_lists()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_select_ciudad(self, _event=None):
        idx = self.ci_list.curselection()
        if not idx:
            return
        i = idx[0]
        if i >= len(self.ci_index):
            return
        _id = self.ci_index[i]
        _id, nombre = self.ciudades_by_id.get(_id, (_id, ""))
        self.ci_selected = _id
        self.ci_nombre.delete(0, tk.END)
        self.ci_nombre.insert(0, nombre)

    def on_update_ciudad(self):
        try:
            cid = getattr(self, "ci_selected", None)
            if not cid:
                raise ValueError("Selecciona una ciudad de la lista")
            nombre = self.ci_nombre.get().strip()
            if not nombre:
                raise ValueError("Nombre requerido")
            update_ciudad(cid, nombre)
            self.refresh_all_lists()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def clear_ciudad_selection(self):
        self.ci_list.selection_clear(0, tk.END)
        self.ci_selected = None
        self.ci_nombre.delete(0, tk.END)

    def on_delete_ciudad(self):
        try:
            cid = getattr(self, "ci_selected", None)
            if not cid:
                raise ValueError("Selecciona una ciudad de la lista")
            if not messagebox.askyesno("Confirmar", "¿Eliminar ciudad seleccionada?"):
                return
            delete_ciudad(cid)
            self.ci_selected = None
            self.refresh_all_lists()
        except sqlite3.IntegrityError:
            messagebox.showerror(
                "Error",
                "No se puede eliminar: hay cargas o bodegas asociadas a esta ciudad.",
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_add_bodega(self):
        try:
            nombre = self.b_nombre.get().strip()
            ciudad_label = self.b_ciudad.get().strip()
            if not nombre:
                raise ValueError("Nombre requerido")
            ciudad_id = self.map_ciudades.get(ciudad_label)
            add_bodega(nombre, ciudad_id)
            self.b_nombre.delete(0, tk.END)
            self.b_ciudad.set("")
            self.refresh_all_lists()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_select_bodega(self, _event=None):
        idx = self.b_list.curselection()
        if not idx:
            return
        i = idx[0]
        if i >= len(self.b_index):
            return
        _id = self.b_index[i]
        _id, nombre, ciudad = self.bodegas_by_id.get(_id, (_id, "", ""))
        self.b_selected = _id
        self.b_nombre.delete(0, tk.END)
        self.b_nombre.insert(0, nombre)
        self.b_ciudad.set(ciudad or "")

    def on_update_bodega(self):
        try:
            bid = getattr(self, "b_selected", None)
            if not bid:
                raise ValueError("Selecciona una bodega de la lista")
            nombre = self.b_nombre.get().strip()
            ciudad_label = self.b_ciudad.get().strip()
            if not nombre:
                raise ValueError("Nombre requerido")
            ciudad_id = self.map_ciudades.get(ciudad_label)
            update_bodega(bid, nombre, ciudad_id)
            self.refresh_all_lists()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def clear_bodega_selection(self):
        self.b_list.selection_clear(0, tk.END)
        self.b_selected = None
        self.b_nombre.delete(0, tk.END)
        self.b_ciudad.set("")

    def on_delete_bodega(self):
        try:
            bid = getattr(self, "b_selected", None)
            if not bid:
                raise ValueError("Selecciona una bodega de la lista")
            if not messagebox.askyesno("Confirmar", "¿Eliminar bodega seleccionada?"):
                return
            delete_bodega(bid)
            self.b_selected = None
            self.refresh_all_lists()
        except sqlite3.IntegrityError:
            messagebox.showerror(
                "Error",
                "No se puede eliminar: hay cargas asociadas a esta bodega.",
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Cargas ----
    def on_save(self):
        try:
            vehiculo_label = self.inputs["vehiculo"].get().strip().upper()
            conductor_label = self.inputs["conductor"].get().strip()
            tipo_label = self.inputs["tipo"].get().strip()
            fcarga = parse_date(self.inputs["fcarga"].get().strip())
            fdesc = parse_date(self.inputs["fdesc"].get().strip())
            origen_label = self.inputs["origen"].get().strip()
            destino_label = self.inputs["destino"].get().strip()
            bodega_origen_label = self.inputs["bodega_origen"].get().strip()
            bodega_destino_label = self.inputs["bodega_destino"].get().strip()
            peso_str = self.inputs["peso"].get().strip()

            if not all([vehiculo_label, conductor_label, tipo_label, origen_label, destino_label, peso_str]):
                raise ValueError("Campos requeridos vacíos.")

            vehiculo_id = self.map_vehiculos.get(vehiculo_label)
            conductor_id = self.map_conductores.get(conductor_label)
            tipo_id = self.map_tipos.get(tipo_label)
            origen_id = self.map_ciudades.get(origen_label)
            destino_id = self.map_ciudades.get(destino_label)
            bodega_origen_id = self.map_bodegas.get(bodega_origen_label) if bodega_origen_label else None
            bodega_destino_id = self.map_bodegas.get(bodega_destino_label) if bodega_destino_label else None

            if not all([vehiculo_id, conductor_id, tipo_id, origen_id, destino_id]):
                raise ValueError("Selecciona valores válidos desde los catálogos.")

            peso = float(peso_str)
            if peso <= 0:
                raise ValueError("El peso debe ser positivo.")

            cid = insert_carga(
                (
                    vehiculo_id,
                    conductor_id,
                    tipo_id,
                    fcarga,
                    fdesc,
                    origen_id,
                    destino_id,
                    bodega_origen_id,
                    bodega_destino_id,
                    peso,
                )
            )
            orden = generate_orden(cid)
            messagebox.showinfo("OK", f"Carga registrada. Orden: {orden}")
            self.on_clear()
            self.refresh_alertas()
            self.refresh_cargas()
        except Exception as e:
            messagebox.showerror("Error", f"Datos inválidos: {e}")

    def on_update_carga(self):
        try:
            if (self.user_info.get("role") or "").lower() == "operador":
                raise ValueError("No tienes permisos para editar cargas.")
            cid = getattr(self, "carga_selected", None)
            if not cid:
                raise ValueError("Selecciona una carga para actualizar (desde la lista).")
            vehiculo_label = self.inputs["vehiculo"].get().strip().upper()
            conductor_label = self.inputs["conductor"].get().strip()
            tipo_label = self.inputs["tipo"].get().strip()
            fcarga = parse_date(self.inputs["fcarga"].get().strip())
            fdesc = parse_date(self.inputs["fdesc"].get().strip())
            origen_label = self.inputs["origen"].get().strip()
            destino_label = self.inputs["destino"].get().strip()
            bodega_origen_label = self.inputs["bodega_origen"].get().strip()
            bodega_destino_label = self.inputs["bodega_destino"].get().strip()
            peso_str = self.inputs["peso"].get().strip()

            if not all([vehiculo_label, conductor_label, tipo_label, origen_label, destino_label, peso_str]):
                raise ValueError("Campos requeridos vacíos.")

            vehiculo_id = self.map_vehiculos.get(vehiculo_label)
            conductor_id = self.map_conductores.get(conductor_label)
            tipo_id = self.map_tipos.get(tipo_label)
            origen_id = self.map_ciudades.get(origen_label)
            destino_id = self.map_ciudades.get(destino_label)
            bodega_origen_id = self.map_bodegas.get(bodega_origen_label) if bodega_origen_label else None
            bodega_destino_id = self.map_bodegas.get(bodega_destino_label) if bodega_destino_label else None

            if not all([vehiculo_id, conductor_id, tipo_id, origen_id, destino_id]):
                raise ValueError("Selecciona valores válidos desde los catálogos.")

            peso = float(peso_str)
            if peso <= 0:
                raise ValueError("El peso debe ser positivo.")

            update_carga(
                cid,
                (
                    vehiculo_id,
                    conductor_id,
                    tipo_id,
                    fcarga,
                    fdesc,
                    origen_id,
                    destino_id,
                    bodega_origen_id,
                    bodega_destino_id,
                    peso,
                ),
            )
            messagebox.showinfo("OK", "Carga actualizada.")
            self.on_clear()
            self.carga_selected = None
            self.lbl_carga_sel.config(text="Carga seleccionada: ninguna")
            self.refresh_alertas()
            self.refresh_cargas()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_clear(self):
        for key, widget in self.inputs.items():
            if isinstance(widget, ttk.Combobox):
                widget.set("")
            else:
                widget.delete(0, tk.END)
        self.carga_selected = None
        self.lbl_carga_sel.config(text="Carga seleccionada: ninguna")

    def on_stats(self):
        try:
            vehiculo_label = self.f_vehiculo.get().strip().upper()
            tipo_label = self.f_tipo.get().strip()
            f_ini = self.f_ini.get().strip()
            f_fin = self.f_fin.get().strip()

            if f_ini:
                parse_date(f_ini)
            if f_fin:
                parse_date(f_fin)

            vehiculo_id = self.map_vehiculos.get(vehiculo_label) if vehiculo_label else None
            tipo_id = self.map_tipos.get(tipo_label) if tipo_label else None

            stats = query_stats((vehiculo_id, tipo_id, f_ini, f_fin))
            self.txt.delete("1.0", tk.END)

            self.lbl_total.config(text=f"Registros: {stats['total_reg']}")
            self.lbl_kg.config(text=f"Total kg: {stats['total_kg']:.2f}")
            self.lbl_avg.config(text=f"Promedio kg: {stats['avg_kg']:.2f}")
            self.lbl_maxmin.config(text=f"Max/Min: {stats['max_kg']:.2f} / {stats['min_kg']:.2f}")

            self.txt.insert(tk.END, "== Por día ==\n")
            for d, s in stats["por_dia"]:
                self.txt.insert(tk.END, f"{d}: {s:.2f} kg\n")
            self.txt.insert(tk.END, "\n")

            self.txt.insert(tk.END, "== Por mes ==\n")
            for m, s, p in stats["por_mes"]:
                self.txt.insert(tk.END, f"{m}: total {s:.2f} kg | promedio {p:.2f} kg\n")
            self.txt.insert(tk.END, "\n")

            self.txt.insert(tk.END, "== Por año ==\n")
            for y, s, p in stats["por_year"]:
                self.txt.insert(tk.END, f"{y}: total {s:.2f} kg | promedio {p:.2f} kg\n")
            self.txt.insert(tk.END, "\n")

            if stats["tipos"]:
                mas = stats["tipos"][0]
                menos = stats["tipos"][-1]
                self.txt.insert(tk.END, "== Tipo de carga más/menos frecuente ==\n")
                self.txt.insert(tk.END, f"Más: {mas[0]} ({mas[1]} veces)\n")
                self.txt.insert(tk.END, f"Menos: {menos[0]} ({menos[1]} veces)\n")
            self.refresh_cargas()
        except Exception as e:
            messagebox.showerror("Error", f"Filtro inválido: {e}")

    def refresh_alertas(self):
        self.alert_list.delete(0, tk.END)
        items = list_alertas()
        for placa, conductor, tipo, f_carga, f_descarga, peso, estado in items:
            line = (
                f"{estado} | Placa: {placa} | Conductor: {conductor} | "
                f"Tipo: {tipo} | Carga: {f_carga} | Descarga: {f_descarga} | {peso:.2f} kg"
            )
            self.alert_list.insert(tk.END, line)

    def refresh_cargas(self):
        if not hasattr(self, "cargas_list"):
            return
        vehiculo_label = self.f_vehiculo.get().strip().upper() if hasattr(self, "f_vehiculo") else ""
        tipo_label = self.f_tipo.get().strip() if hasattr(self, "f_tipo") else ""
        f_ini = self.f_ini.get().strip() if hasattr(self, "f_ini") else ""
        f_fin = self.f_fin.get().strip() if hasattr(self, "f_fin") else ""
        term = self.cargas_search.get().strip().lower() if hasattr(self, "cargas_search") else ""

        vehiculo_id = self.map_vehiculos.get(vehiculo_label) if vehiculo_label else None
        tipo_id = self.map_tipos.get(tipo_label) if tipo_label else None

        items = list_cargas((vehiculo_id, tipo_id, f_ini, f_fin))
        self.cargas_list.delete(0, tk.END)
        self.cargas_ids = []
        for cid, orden, placa, conductor, tipo, f_carga, f_descarga, peso in items:
            if term:
                hay = f"{orden} {placa} {conductor} {tipo}".lower()
                if term not in hay:
                    continue
            line = (
                f"ID:{cid} | Orden: {orden} | Placa: {placa} | Conductor: {conductor} | "
                f"Tipo: {tipo} | Carga: {f_carga} | Descarga: {f_descarga} | {peso:.2f} kg"
            )
            self.cargas_list.insert(tk.END, line)
            self.cargas_ids.append(cid)

    def on_delete_carga(self):
        try:
            if (self.user_info.get("role") or "").lower() == "operador":
                raise ValueError("No tienes permisos para eliminar cargas.")
            idx = self.cargas_list.curselection()
            if not idx:
                raise ValueError("Selecciona una carga de la lista")
            i = idx[0]
            if i >= len(self.cargas_ids):
                return
            cid = self.cargas_ids[i]
            if not messagebox.askyesno("Confirmar", "¿Eliminar carga seleccionada?"):
                return
            delete_carga(cid)
            self.refresh_cargas()
            self.refresh_alertas()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def clear_cargas_search(self):
        if hasattr(self, "cargas_search"):
            self.cargas_search.delete(0, tk.END)
        self.refresh_cargas()

    def refresh_ordenes(self):
        if not hasattr(self, "o_list"):
            return
        term = self.o_search.get().strip().lower()
        vehiculo_label = self.o_vehiculo.get().strip().upper()
        tipo_label = self.o_tipo.get().strip()
        f_ini = self.o_ini.get().strip()
        f_fin = self.o_fin.get().strip()

        has_filter = any([term, vehiculo_label, tipo_label, f_ini, f_fin])
        if not has_filter:
            self.o_list.delete(0, tk.END)
            self.o_ids = []
            if hasattr(self, "o_det"):
                self.o_det.delete("1.0", tk.END)
            if hasattr(self, "o_msg"):
                self.o_msg.config(text="Usa un filtro o búsqueda para ver resultados.")
            return

        if f_ini:
            parse_date(f_ini)
        if f_fin:
            parse_date(f_fin)

        vehiculo_id = self.map_vehiculos.get(vehiculo_label) if vehiculo_label else None
        tipo_id = self.map_tipos.get(tipo_label) if tipo_label else None

        items = list_cargas((vehiculo_id, tipo_id, f_ini, f_fin))
        self.o_list.delete(0, tk.END)
        self.o_ids = []
        for cid, orden, placa, conductor, tipo, f_carga, f_descarga, peso in items:
            hay = f"{orden} {placa} {conductor} {tipo}".lower()
            if term and term not in hay:
                continue
            line = (
                f"Orden: {orden} | Placa: {placa} | Conductor: {conductor} | "
                f"Tipo: {tipo} | Carga: {f_carga} | Descarga: {f_descarga} | {peso:.2f} kg"
            )
            self.o_list.insert(tk.END, line)
            self.o_ids.append(cid)
        if hasattr(self, "o_msg"):
            self.o_msg.config(text=f"Resultados: {len(self.o_ids)}")

    def on_select_orden(self, _event=None):
        idx = self.o_list.curselection()
        if not idx:
            return
        i = idx[0]
        if i >= len(self.o_ids):
            return
        cid = self.o_ids[i]
        self.o_selected = cid
        row = get_carga(cid)
        if not row:
            return
        (
            _id,
            orden,
            placa,
            conductor_nombre,
            conductor_cedula,
            tipo,
            f_carga,
            f_descarga,
            origen,
            destino,
            bodega_origen,
            bodega_destino,
            peso,
        ) = row
        conductor_label = (
            f"{conductor_nombre} (CC {conductor_cedula})" if conductor_cedula else conductor_nombre
        )
        detail = [
            f"Orden: {orden}",
            f"Placa: {placa}",
            f"Conductor: {conductor_label}",
            f"Tipo de carga: {tipo}",
            f"Peso: {peso:.2f} kg",
            "",
            f"Fecha carga: {f_carga}",
            f"Fecha descarga: {f_descarga}",
            f"Origen: {origen}",
            f"Destino: {destino}",
            f"Bodega origen: {bodega_origen or '-'}",
            f"Bodega destino: {bodega_destino or '-'}",
        ]
        self.o_det.delete("1.0", tk.END)
        self.o_det.insert(tk.END, "\n".join(detail))

    def clear_ordenes_filters(self):
        self.o_search.delete(0, tk.END)
        self.o_vehiculo.set("")
        self.o_tipo.set("")
        self.o_ini.delete(0, tk.END)
        self.o_fin.delete(0, tk.END)
        self.refresh_ordenes()

    def refresh_users(self):
        if not hasattr(self, "u_list"):
            return
        term = self.u_search.get().strip().lower()
        items = list_users()
        self.u_list.delete(0, tk.END)
        self.u_ids = []
        for uid, username, nombre, cedula, role, activo in items:
            label = f"{username} | {nombre} | {cedula} | {role} | {'activo' if activo else 'inactivo'}"
            if term and term not in label.lower():
                continue
            self.u_list.insert(tk.END, label)
            self.u_ids.append(uid)

    def on_select_user(self, _event=None):
        idx = self.u_list.curselection()
        if not idx:
            return
        i = idx[0]
        if i >= len(self.u_ids):
            return
        uid = self.u_ids[i]
        rows = list_users()
        user = next((u for u in rows if u[0] == uid), None)
        if not user:
            return
        _, username, nombre, cedula, role, activo = user
        self.u_selected = uid
        self.u_username.delete(0, tk.END)
        self.u_username.insert(0, username)
        self.u_nombre.delete(0, tk.END)
        self.u_nombre.insert(0, nombre)
        self.u_cedula.delete(0, tk.END)
        self.u_cedula.insert(0, cedula)
        self.u_role.set(role)
        self.u_password.delete(0, tk.END)
        self.u_active.set(1 if activo else 0)

    def clear_users_form(self):
        self.u_username.delete(0, tk.END)
        self.u_nombre.delete(0, tk.END)
        self.u_cedula.delete(0, tk.END)
        self.u_role.set("")
        self.u_password.delete(0, tk.END)
        self.u_active.set(1)
        self.u_selected = None
        if hasattr(self, "u_search"):
            self.u_search.delete(0, tk.END)
        self.refresh_users()

    def on_create_user(self):
        try:
            username = self.u_username.get().strip()
            nombre = self.u_nombre.get().strip()
            cedula = self.u_cedula.get().strip()
            role = self.u_role.get().strip()
            password = self.u_password.get().strip()
            if not username or not role or not password:
                raise ValueError("Usuario, rol y contraseña son requeridos.")
            add_user(username, password, role, nombre, cedula)
            self.clear_users_form()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_update_user(self):
        try:
            uid = getattr(self, "u_selected", None)
            if not uid:
                raise ValueError("Selecciona un usuario.")
            username = self.u_username.get().strip()
            nombre = self.u_nombre.get().strip()
            cedula = self.u_cedula.get().strip()
            role = self.u_role.get().strip()
            password = self.u_password.get().strip() or None
            activo = self.u_active.get()
            if not username or not role:
                raise ValueError("Usuario y rol son requeridos.")
            update_user(uid, username, role, nombre, cedula, password=password, activo=activo)
            self.clear_users_form()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_deactivate_user(self):
        try:
            uid = getattr(self, "u_selected", None)
            if not uid:
                raise ValueError("Selecciona un usuario.")
            if not messagebox.askyesno("Confirmar", "¿Desactivar este usuario?"):
                return
            deactivate_user(uid)
            self.clear_users_form()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_reactivate_user(self):
        try:
            uid = getattr(self, "u_selected", None)
            if not uid:
                raise ValueError("Selecciona un usuario.")
            if not messagebox.askyesno("Confirmar", "¿Reactivar este usuario?"):
                return
            reactivate_user(uid)
            self.clear_users_form()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_edit_orden(self):
        try:
            cid = getattr(self, "o_selected", None)
            if not cid:
                raise ValueError("Selecciona una orden de la lista")
            self.on_edit_carga(cid)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_print_orden(self):
        try:
            cid = getattr(self, "o_selected", None)
            if not cid:
                raise ValueError("Selecciona una orden de la lista")
            self.on_print_carga(cid)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_pdf_orden(self):
        try:
            cid = getattr(self, "o_selected", None)
            if not cid:
                raise ValueError("Selecciona una orden de la lista")
            self.on_pdf_carga(cid)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_carga_id(self):
        idx = self.cargas_list.curselection()
        if idx:
            i = idx[0]
            if i < len(self.cargas_ids):
                return self.cargas_ids[i]
        return getattr(self, "carga_selected", None)

    def on_edit_carga(self, cid=None):
        try:
            if cid is None:
                cid = self._selected_carga_id()
            if not cid:
                raise ValueError("Selecciona una carga de la lista")
            row = get_carga(cid)
            if not row:
                raise ValueError("No se encontró la carga.")
            (
                _id,
                orden,
                placa,
                conductor_nombre,
                conductor_cedula,
                tipo,
                f_carga,
                f_descarga,
                origen,
                destino,
                bodega_origen,
                bodega_destino,
                peso,
            ) = row
            conductor_label = (
                f"{conductor_cedula} - {conductor_nombre}" if conductor_cedula else conductor_nombre
            )

            self.inputs["vehiculo"].set(placa)
            self.inputs["conductor"].set(conductor_label)
            self.inputs["tipo"].set(tipo)
            self.inputs["fcarga"].delete(0, tk.END)
            self.inputs["fcarga"].insert(0, f_carga)
            self.inputs["fdesc"].delete(0, tk.END)
            self.inputs["fdesc"].insert(0, f_descarga)
            self.inputs["origen"].set(origen)
            self.inputs["destino"].set(destino)
            self.inputs["bodega_origen"].set(bodega_origen or "")
            self.inputs["bodega_destino"].set(bodega_destino or "")
            self.inputs["peso"].delete(0, tk.END)
            self.inputs["peso"].insert(0, f"{peso:.2f}")

            self.carga_selected = cid
            self.lbl_carga_sel.config(text=f"Carga seleccionada: ID {cid} | Orden {orden}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _build_recibo(self, row):
        (
            _id,
            orden,
            placa,
            conductor_nombre,
            conductor_cedula,
            tipo,
            f_carga,
            f_descarga,
            origen,
            destino,
            bodega_origen,
            bodega_destino,
            peso,
        ) = row
        fecha = datetime.today().strftime("%Y-%m-%d %H:%M")
        conductor_label = (
            f"{conductor_nombre} (CC {conductor_cedula})" if conductor_cedula else conductor_nombre
        )
        header = get_config("encabezado") or "RECIBO DE CARGA"
        nit = get_config("nit")
        direccion = get_config("direccion")
        telefono = get_config("telefono")
        lines = [
            header,
            f"NIT: {nit}" if nit else "",
            f"Dirección: {direccion}" if direccion else "",
            f"Teléfono: {telefono}" if telefono else "",
            f"Orden: {orden}",
            f"Fecha impresión: {fecha}",
            "",
            f"Placa: {placa}",
            f"Conductor: {conductor_label}",
            f"Tipo de carga: {tipo}",
            f"Peso: {peso:.2f} kg",
            "",
            f"Fecha carga: {f_carga}",
            f"Fecha descarga: {f_descarga}",
            f"Origen: {origen}",
            f"Destino: {destino}",
            f"Bodega origen: {bodega_origen or '-'}",
            f"Bodega destino: {bodega_destino or '-'}",
            "",
            "______________________________",
            "Recibido por",
            "",
            "______________________________",
            "Entregado por",
        ]
        return "\n".join([l for l in lines if l != ""])

    def on_print_carga(self, cid=None):
        try:
            if cid is None:
                cid = self._selected_carga_id()
            if not cid:
                raise ValueError("Selecciona una carga de la lista")
            row = get_carga(cid)
            if not row:
                raise ValueError("No se encontró la carga.")
            recibo = self._build_recibo(row)

            win = tk.Toplevel(self)
            win.title("Recibo de carga")
            win.geometry("520x520")
            win.resizable(False, False)

            header = get_config("encabezado") or "RECIBO DE CARGA"
            logo_path = get_config("logo_path")
            orden = row[1]

            head = ttk.Label(win, text=header, font=("Helvetica", 14, "bold"))
            head.pack(pady=(8, 0))

            if logo_path and os.path.exists(logo_path):
                try:
                    img = tk.PhotoImage(file=logo_path)
                    self._print_logo_ref = img
                    ttk.Label(win, image=img).pack(pady=6)
                except Exception:
                    ttk.Label(win, text=f"[Logo no compatible: {logo_path}]").pack(pady=4)

            # QR preview (order only)
            try:
                import qrcode  # type: ignore
                qr_img = qrcode.make(f"SISTEMA_DE_CARGAS|ORDEN:{orden}")
                qr_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                qr_img.save(qr_path)
                qr_photo = tk.PhotoImage(file=qr_path)
                self._qr_preview_ref = qr_photo
                ttk.Label(win, image=qr_photo).pack(pady=4)
                try:
                    os.remove(qr_path)
                except Exception:
                    pass
            except Exception:
                pass

            txt = tk.Text(win, width=64, height=24)
            txt.pack(padx=10, pady=10)
            txt.insert(tk.END, recibo)
            txt.config(state="disabled")

            btns = ttk.Frame(win)
            btns.pack(pady=6)

            def save_txt():
                path = filedialog.asksaveasfilename(
                    title="Guardar recibo",
                    defaultextension=".txt",
                    filetypes=[("Texto", "*.txt")],
                )
                if not path:
                    return
                with open(path, "w", encoding="utf-8") as f:
                    f.write(recibo)
                messagebox.showinfo("OK", "Recibo guardado.")

            def do_print():
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
                        f.write(recibo.encode("utf-8"))
                        temp_path = f.name
                    if sys.platform.startswith("win"):
                        os.startfile(temp_path, "print")
                    else:
                        subprocess.run(["lpr", temp_path], check=False)
                    messagebox.showinfo("OK", "Enviado a impresión.")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo imprimir: {e}")

            ttk.Button(btns, text="Guardar TXT", command=save_txt).pack(side="left", padx=6)
            ttk.Button(btns, text="Imprimir", command=do_print).pack(side="left", padx=6)
            ttk.Button(btns, text="Guardar PDF", command=lambda: self.on_pdf_carga(cid)).pack(
                side="left", padx=6
            )
            ttk.Button(btns, text="Cerrar", command=win.destroy).pack(side="left", padx=6)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_pdf_carga(self, cid=None):
        try:
            if cid is None:
                cid = self._selected_carga_id()
            if not cid:
                raise ValueError("Selecciona una carga de la lista")
            row = get_carga(cid)
            if not row:
                raise ValueError("No se encontró la carga.")
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.lib import colors
                from reportlab.pdfgen import canvas
            except Exception:
                raise ValueError("Falta reportlab. Instala: pip install reportlab")
            try:
                import qrcode  # type: ignore
            except Exception:
                raise ValueError("Falta qrcode. Instala: pip install qrcode[pil]")

            (
                _id,
                orden,
                placa,
                conductor_nombre,
                conductor_cedula,
                tipo,
                f_carga,
                f_descarga,
                origen,
                destino,
                bodega_origen,
                bodega_destino,
                peso,
            ) = row

            path = filedialog.asksaveasfilename(
                title="Guardar PDF",
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
                initialfile=f"{orden}.pdf",
            )
            if not path:
                return
            header = get_config("encabezado") or "RECIBO DE CARGA"
            logo_path = get_config("logo_path")
            nit = get_config("nit")
            direccion = get_config("direccion")
            telefono = get_config("telefono")

            half_letter = (8.5 * 72, 5.5 * 72)
            c = canvas.Canvas(path, pagesize=half_letter)
            width, height = half_letter
            margin = 36
            y = height - margin

            # Subtle background and header band
            c.setFillColor(colors.whitesmoke)
            c.rect(0, 0, width, height, stroke=0, fill=1)
            c.setFillColor(colors.Color(0.92, 0.92, 0.92))
            c.rect(0, height - 80, width, 80, stroke=0, fill=1)
            c.setFillColor(colors.black)

            # Header area
            if logo_path and os.path.exists(logo_path):
                try:
                    c.drawImage(
                        logo_path,
                        margin,
                        height - margin - 50,
                        width=90,
                        height=50,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                except Exception:
                    pass
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(width / 2, height - margin - 10, header)

            # Company info (top-right block)
            c.setFont("Helvetica", 9)
            info_x = width - margin - 220
            info_y = height - margin - 10
            info_lines = [
                f"NIT: {nit}" if nit else "",
                f"Dirección: {direccion}" if direccion else "",
                f"Teléfono: {telefono}" if telefono else "",
            ]
            for line in [l for l in info_lines if l]:
                c.drawString(info_x, info_y, line)
                info_y -= 12

            c.setFont("Helvetica", 11)
            fecha = datetime.today().strftime("%Y-%m-%d %H:%M")
            conductor_label = (
                f"{conductor_nombre} (CC {conductor_cedula})" if conductor_cedula else conductor_nombre
            )

            qr_data = f"SISTEMA_DE_CARGAS|ORDEN:{orden}"
            qr_img = qrcode.make(qr_data)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
                qr_path = f.name
                qr_img.save(qr_path)

            # QR (top-right corner, below info)
            qr_y = height - margin - 90
            try:
                c.drawImage(qr_path, width - margin - 90, qr_y, width=80, height=80, mask="auto")
            except Exception:
                pass

            # Section box for content
            box_left = margin
            box_right = width - margin - 110
            box_top = height - margin - 90
            box_bottom = 95
            c.setStrokeColor(colors.grey)
            c.setLineWidth(0.6)
            c.rect(box_left, box_bottom, box_right - box_left, box_top - box_bottom, stroke=1, fill=0)

            c.setFillColor(colors.Color(0.85, 0.85, 0.85))
            c.rect(box_left, box_top - 18, box_right - box_left, 18, stroke=0, fill=1)
            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(box_left + 6, box_top - 14, "DETALLE DE CARGA")

            y = box_top - 30
            lines = [
                f"Orden: {orden}",
                f"Fecha impresión: {fecha}",
                f"Orden elaborada por sistema: {APP_NAME}",
                "",
                f"Placa: {placa}",
                f"Conductor: {conductor_label}",
                f"Tipo de carga: {tipo}",
                f"Peso: {peso:.2f} kg",
                "",
                f"Fecha carga: {f_carga}",
                f"Fecha descarga: {f_descarga}",
                f"Origen: {origen}",
                f"Destino: {destino}",
                f"Bodega origen: {bodega_origen or '-'}",
                f"Bodega destino: {bodega_destino or '-'}",
            ]
            c.setFont("Helvetica", 10)
            text_x = box_left + 6
            text_y = y
            for line in [l for l in lines if l != ""]:
                c.drawString(text_x, text_y, line)
                text_y -= 13

            # Signature area (bottom, two columns)
            sig_y = 60
            c.line(margin, sig_y, width / 2 - 20, sig_y)
            c.line(width / 2 + 20, sig_y, width - margin, sig_y)
            c.setFont("Helvetica", 10)
            c.drawString(margin, sig_y - 14, "Recibido por")
            c.drawString(width / 2 + 20, sig_y - 14, "Entregado por")

            c.save()
            try:
                os.remove(qr_path)
            except Exception:
                pass
            messagebox.showinfo("OK", "PDF guardado.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load_config(self):
        if not hasattr(self, "cfg_header"):
            return
        self.cfg_header.delete(0, tk.END)
        self.cfg_header.insert(0, get_config("encabezado"))
        self.cfg_nit.delete(0, tk.END)
        self.cfg_nit.insert(0, get_config("nit"))
        self.cfg_dir.delete(0, tk.END)
        self.cfg_dir.insert(0, get_config("direccion"))
        self.cfg_tel.delete(0, tk.END)
        self.cfg_tel.insert(0, get_config("telefono"))
        self.cfg_logo.delete(0, tk.END)
        self.cfg_logo.insert(0, get_config("logo_path"))
        self._refresh_logo_preview()

    def on_save_config(self):
        try:
            header = self.cfg_header.get().strip()
            logo = self.cfg_logo.get().strip()
            nit = self.cfg_nit.get().strip()
            direccion = self.cfg_dir.get().strip()
            telefono = self.cfg_tel.get().strip()
            set_config("encabezado", header)
            set_config("logo_path", logo)
            set_config("nit", nit)
            set_config("direccion", direccion)
            set_config("telefono", telefono)
            self._refresh_logo_preview()
            messagebox.showinfo("OK", "Configuración guardada.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_browse_logo(self):
        path = filedialog.askopenfilename(
            title="Seleccionar logo (PNG)",
            filetypes=[("PNG", "*.png")],
        )
        if not path:
            return
        self.cfg_logo.delete(0, tk.END)
        self.cfg_logo.insert(0, path)
        self._refresh_logo_preview()

    def _refresh_logo_preview(self):
        path = self.cfg_logo.get().strip() if hasattr(self, "cfg_logo") else ""
        if not path or not os.path.exists(path):
            self.cfg_logo_preview.config(text="Sin logo", image="")
            return
        try:
            img = tk.PhotoImage(file=path)
            self._logo_ref = img
            self.cfg_logo_preview.config(image=img, text="")
        except Exception:
            self.cfg_logo_preview.config(text="Logo no compatible", image="")

    def export_cargas_csv(self):
        try:
            path = filedialog.asksaveasfilename(
                title="Guardar CSV",
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
            )
            if not path:
                return
            import csv

            items = list_cargas((None, None, "", ""))
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["id", "orden", "placa", "conductor", "tipo", "fecha_carga", "fecha_descarga", "peso"])
                for cid, orden, placa, conductor, tipo, f_carga, f_descarga, peso in items:
                    w.writerow([cid, orden, placa, conductor, tipo, f_carga, f_descarga, f"{peso:.2f}"])
            messagebox.showinfo("OK", "CSV exportado.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def export_cargas_excel(self):
        try:
            try:
                import openpyxl  # type: ignore
            except Exception:
                raise ValueError("Falta openpyxl. Instala: pip install openpyxl")
            path = filedialog.asksaveasfilename(
                title="Guardar Excel",
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
            )
            if not path:
                return
            items = list_cargas((None, None, "", ""))
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Cargas"
            ws.append(["id", "orden", "placa", "conductor", "tipo", "fecha_carga", "fecha_descarga", "peso"])
            for cid, orden, placa, conductor, tipo, f_carga, f_descarga, peso in items:
                ws.append([cid, orden, placa, conductor, tipo, f_carga, f_descarga, float(peso)])
            wb.save(path)
            messagebox.showinfo("OK", "Excel exportado.")
        except Exception as e:
            messagebox.showerror("Error", str(e))


if __name__ == "__main__":
    init_db()
    user_info = login_dialog()
    if user_info:
        app = App(user_info=user_info)
        app.mainloop()
