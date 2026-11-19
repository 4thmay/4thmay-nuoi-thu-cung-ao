import datetime
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import psycopg2
    import psycopg2.extras
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    HAS_PSYCOPG2 = True
except Exception:
    HAS_PSYCOPG2 = False

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tamaweb.db")
PG_DB_NAME = os.environ.get("PG_DB_NAME", "tamaweb_db")
DATABASE_URL = os.environ.get("DATABASE_URL", f"postgresql://localhost:5432/{PG_DB_NAME}")

LOCK_DURATION_SECONDS = {
    "1h": (3600, "1 Giờ"),
    "24h": (86400, "24 Giờ (1 Ngày)"),
    "3d": (3 * 86400, "3 Ngày"),
    "7d": (7 * 86400, "7 Ngày"),
    "30d": (30 * 86400, "30 Ngày"),
    "permanent": (0, "Vĩnh viễn"),
}


def hash_password(password: str, salt: Optional[str] = None) -> str:
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str, stored_plain: str = "") -> bool:
    if stored_plain and hmac.compare_digest(password, stored_plain):
        return True
    try:
        if not stored_hash:
            return False
        if "$" not in stored_hash:
            return hmac.compare_digest(password, stored_hash)
        salt, _ = stored_hash.split("$", 1)
        return hmac.compare_digest(hash_password(password, salt), stored_hash)
    except Exception:
        return False


def format_timestamp(ts: Optional[float], include_seconds: bool = False) -> str:
    if not ts or ts <= 0:
        return "Chưa ghi nhận"
    try:
        dt = datetime.datetime.fromtimestamp(float(ts))
        return dt.strftime("%d/%m/%Y %H:%M:%S" if include_seconds else "%d/%m/%Y %H:%M")
    except Exception:
        return "Chưa ghi nhận"


def ensure_postgres_database() -> bool:
    """Tự động tạo database PostgreSQL `tamaweb_db` trên localhost:5432 nếu chưa tồn tại"""
    if not HAS_PSYCOPG2:
        return False
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        pass

    for default_dsn in ("postgresql://localhost:5432/postgres", "postgresql://postgres@localhost:5432/postgres"):
        try:
            conn = psycopg2.connect(default_dsn, connect_timeout=2)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (PG_DB_NAME,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{PG_DB_NAME}"')
            cur.close()
            conn.close()
            return True
        except Exception:
            continue
    return False


def _get_pg_conn():
    if not HAS_PSYCOPG2:
        return None
    try:
        return psycopg2.connect(DATABASE_URL, connect_timeout=2)
    except Exception:
        if ensure_postgres_database():
            try:
                return psycopg2.connect(DATABASE_URL, connect_timeout=2)
            except Exception:
                return None
    return None


def is_using_postgres() -> bool:
    conn = _get_pg_conn()
    if conn is not None:
        conn.close()
        return True
    return False


def init_db():
    now = time.time()

    user_alter_cols_pg = [
        ("status", "VARCHAR(24) DEFAULT 'active'"),
        ("is_online", "INTEGER DEFAULT 0"),
        ("last_login_at", "DOUBLE PRECISION DEFAULT 0"),
        ("last_active_at", "DOUBLE PRECISION DEFAULT 0"),
        ("login_count", "INTEGER DEFAULT 0"),
        ("last_device", "TEXT DEFAULT 'Web Browser (Tamaweb WASM)'"),
        ("streak_days", "INTEGER DEFAULT 1"),
        ("last_streak_date", "VARCHAR(16) DEFAULT ''"),
        ("lock_reason", "TEXT DEFAULT ''"),
        ("locked_until", "DOUBLE PRECISION DEFAULT 0"),
        ("locked_by", "VARCHAR(64) DEFAULT ''"),
        ("locked_at", "DOUBLE PRECISION DEFAULT 0"),
        ("lock_duration_label", "TEXT DEFAULT ''"),
    ]

    user_alter_cols_sqlite = [
        ("status", "TEXT DEFAULT 'active'"),
        ("is_online", "INTEGER DEFAULT 0"),
        ("last_login_at", "REAL DEFAULT 0"),
        ("last_active_at", "REAL DEFAULT 0"),
        ("login_count", "INTEGER DEFAULT 0"),
        ("last_device", "TEXT DEFAULT 'Web Browser (Tamaweb WASM)'"),
        ("streak_days", "INTEGER DEFAULT 1"),
        ("last_streak_date", "TEXT DEFAULT ''"),
        ("lock_reason", "TEXT DEFAULT ''"),
        ("locked_until", "REAL DEFAULT 0"),
        ("locked_by", "TEXT DEFAULT ''"),
        ("locked_at", "REAL DEFAULT 0"),
        ("lock_duration_label", "TEXT DEFAULT ''"),
    ]

    # 1. Khởi tạo trên PostgreSQL (nếu PostgreSQL đang chạy)
    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            cur = pg_conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(64) UNIQUE NOT NULL,
                password TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role VARCHAR(20) DEFAULT 'user',
                created_at DOUBLE PRECISION,
                status VARCHAR(24) DEFAULT 'active',
                is_online INTEGER DEFAULT 0,
                last_login_at DOUBLE PRECISION DEFAULT 0,
                last_active_at DOUBLE PRECISION DEFAULT 0,
                login_count INTEGER DEFAULT 0,
                last_device TEXT DEFAULT 'Web Browser (Tamaweb WASM)',
                streak_days INTEGER DEFAULT 1,
                last_streak_date VARCHAR(16) DEFAULT '',
                lock_reason TEXT DEFAULT '',
                locked_until DOUBLE PRECISION DEFAULT 0,
                locked_by VARCHAR(64) DEFAULT '',
                locked_at DOUBLE PRECISION DEFAULT 0,
                lock_duration_label TEXT DEFAULT ''
            )
            """)
            for col_name, col_def in user_alter_cols_pg:
                try:
                    cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_def}")
                except Exception:
                    pg_conn.rollback()

            cur.execute("""
            CREATE TABLE IF NOT EXISTS pets (
                user_id VARCHAR(64) PRIMARY KEY,
                pet_name TEXT,
                stage INTEGER,
                character_file TEXT,
                level INTEGER,
                exp INTEGER,
                hunger DOUBLE PRECISION,
                energy DOUBLE PRECISION,
                hygiene DOUBLE PRECISION,
                happiness DOUBLE PRECISION,
                age_seconds INTEGER,
                full_state_json TEXT,
                updated_at DOUBLE PRECISION
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(64) UNIQUE,
                pet_name TEXT,
                stage_name TEXT,
                level INTEGER,
                age_seconds INTEGER,
                score INTEGER,
                updated_at DOUBLE PRECISION
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS analytics (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(64),
                event_name TEXT,
                payload_json TEXT,
                created_at DOUBLE PRECISION
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS account_lock_history (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(64) NOT NULL,
                action TEXT NOT NULL,
                reason TEXT DEFAULT '',
                duration_label TEXT DEFAULT '',
                locked_until DOUBLE PRECISION DEFAULT 0,
                performed_by VARCHAR(64) DEFAULT 'admin',
                created_at DOUBLE PRECISION
            )
            """)
            pg_conn.commit()
            cur.close()
            pg_conn.close()
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    # 2. Luôn đồng bộ bảng trên SQLite để đảm bảo an toàn dữ liệu
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        created_at REAL,
        status TEXT DEFAULT 'active',
        is_online INTEGER DEFAULT 0,
        last_login_at REAL DEFAULT 0,
        last_active_at REAL DEFAULT 0,
        login_count INTEGER DEFAULT 0,
        last_device TEXT DEFAULT 'Web Browser (Tamaweb WASM)',
        streak_days INTEGER DEFAULT 1,
        last_streak_date TEXT DEFAULT '',
        lock_reason TEXT DEFAULT '',
        locked_until REAL DEFAULT 0,
        locked_by TEXT DEFAULT '',
        locked_at REAL DEFAULT 0,
        lock_duration_label TEXT DEFAULT ''
    )
    """)

    for col_name, col_def in user_alter_cols_sqlite:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pets (
        user_id TEXT PRIMARY KEY,
        pet_name TEXT,
        stage INTEGER,
        character_file TEXT,
        level INTEGER,
        exp INTEGER,
        hunger REAL,
        energy REAL,
        hygiene REAL,
        happiness REAL,
        age_seconds INTEGER,
        full_state_json TEXT,
        updated_at REAL
    )
    """)

    try:
        cursor.execute("ALTER TABLE pets ADD COLUMN full_state_json TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leaderboard (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT UNIQUE,
        pet_name TEXT,
        stage_name TEXT,
        level INTEGER,
        age_seconds INTEGER,
        score INTEGER,
        updated_at REAL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        event_name TEXT,
        payload_json TEXT,
        created_at REAL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS account_lock_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        action TEXT NOT NULL,
        reason TEXT DEFAULT '',
        duration_label TEXT DEFAULT '',
        locked_until REAL DEFAULT 0,
        performed_by TEXT DEFAULT 'admin',
        created_at REAL
    )
    """)

    conn.commit()
    conn.close()

    # 3. Đảm bảo tài khoản quản trị viên mặc định (admin / admin123) và dữ liệu mẫu luôn sẵn sàng
    _seed_initial_accounts_and_saves(now)


def _sync_postgres_and_sqlite():
    """Đồng bộ hai chiều giữa PostgreSQL (Render Cloud) và SQLite để không mất tài khoản khi deploy"""
    pg_conn = _get_pg_conn()
    if pg_conn is None:
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        pcur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 1. Kéo toàn bộ users từ PostgreSQL về SQLite nếu SQLite chưa có
        pcur.execute("SELECT * FROM users ORDER BY id ASC")
        for prow in pcur.fetchall():
            uname = prow["username"]
            cur.execute("SELECT id FROM users WHERE username = ?", (uname,))
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO users (
                        username, password, password_hash, role, created_at,
                        status, is_online, last_login_at, last_active_at, login_count,
                        last_device, streak_days, last_streak_date,
                        lock_reason, locked_until, locked_by, locked_at, lock_duration_label
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    uname, prow.get("password", "123456"), prow.get("password_hash", ""),
                    prow.get("role", "user"), prow.get("created_at", time.time()),
                    prow.get("status", "active"), prow.get("is_online", 0),
                    prow.get("last_login_at", 0), prow.get("last_active_at", 0),
                    prow.get("login_count", 1), prow.get("last_device", "Web Browser (Tamaweb WASM)"),
                    prow.get("streak_days", 1), prow.get("last_streak_date", ""),
                    prow.get("lock_reason", ""), prow.get("locked_until", 0),
                    prow.get("locked_by", ""), prow.get("locked_at", 0),
                    prow.get("lock_duration_label", ""),
                ))

        # 2. Đẩy toàn bộ users từ SQLite lên PostgreSQL nếu PostgreSQL chưa có
        cur.execute("SELECT * FROM users ORDER BY id ASC")
        for srow in cur.fetchall():
            sd = dict(srow)
            uname = sd["username"]
            pcur.execute("SELECT id FROM users WHERE username = %s", (uname,))
            if not pcur.fetchone():
                pcur.execute("""
                    INSERT INTO users (
                        username, password, password_hash, role, created_at,
                        status, is_online, last_login_at, last_active_at, login_count,
                        last_device, streak_days, last_streak_date,
                        lock_reason, locked_until, locked_by, locked_at, lock_duration_label
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    uname, sd.get("password", "123456"), sd.get("password_hash", ""),
                    sd.get("role", "user"), sd.get("created_at", time.time()),
                    sd.get("status", "active"), sd.get("is_online", 0),
                    sd.get("last_login_at", 0), sd.get("last_active_at", 0),
                    sd.get("login_count", 1), sd.get("last_device", "Web Browser (Tamaweb WASM)"),
                    sd.get("streak_days", 1), sd.get("last_streak_date", ""),
                    sd.get("lock_reason", ""), sd.get("locked_until", 0),
                    sd.get("locked_by", ""), sd.get("locked_at", 0),
                    sd.get("lock_duration_label", ""),
                ))

        # 3. Kéo pets từ PostgreSQL về SQLite nếu chưa có
        pcur.execute("SELECT * FROM pets")
        for prow in pcur.fetchall():
            uid = prow["user_id"]
            cur.execute("SELECT user_id FROM pets WHERE user_id = ?", (uid,))
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO pets (
                        user_id, pet_name, stage, character_file, level, exp,
                        hunger, energy, hygiene, happiness, age_seconds, full_state_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    uid, prow.get("pet_name"), prow.get("stage", 1), prow.get("character_file"),
                    prow.get("level", 1), prow.get("exp", 0), prow.get("hunger", 100.0),
                    prow.get("energy", 100.0), prow.get("hygiene", 100.0), prow.get("happiness", 100.0),
                    prow.get("age_seconds", 0), prow.get("full_state_json"), prow.get("updated_at", time.time()),
                ))

        conn.commit()
        pg_conn.commit()
        pcur.close()
        pg_conn.close()
        conn.close()
    except Exception:
        try:
            pg_conn.close()
        except Exception:
            pass


def _seed_initial_accounts_and_saves(now: float):
    """Đảm bảo tài khoản admin/admin123 tồn tại và đồng bộ các file local_save_*.json vào DB"""
    _sync_postgres_and_sqlite()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Đảm bảo tài khoản admin / admin123 tồn tại
    cur.execute("SELECT * FROM users WHERE username = 'admin'")
    admin_row = cur.fetchone()
    admin_pw_hash = hash_password("admin123")
    today_str = datetime.date.today().isoformat()
    if not admin_row:
        cur.execute("""
            INSERT INTO users (
                username, password, password_hash, role, created_at,
                status, is_online, last_login_at, last_active_at, login_count,
                last_device, streak_days, last_streak_date
            ) VALUES (?, ?, ?, 'admin', ?, 'active', 1, ?, ?, 15, 'Admin Console (macOS / Web)', 12, ?)
        """, ("admin", "admin123", admin_pw_hash, now - 7 * 86400, now, now, today_str))
    else:
        cur.execute("""
            UPDATE users SET role = 'admin', status = 'active'
            WHERE username = 'admin'
        """)

    # 2. Cập nhật các tài khoản cũ chưa có metadata đầy đủ
    cur.execute("SELECT id, username, created_at, last_login_at, login_count, status, last_device, streak_days FROM users")
    existing_users = [dict(r) for r in cur.fetchall()]
    for u in existing_users:
        uname = u["username"]
        c_at = u["created_at"] or (now - 86400)
        l_at = u["last_login_at"] if (u["last_login_at"] and u["last_login_at"] > 0) else c_at
        l_cnt = u["login_count"] if (u["login_count"] and u["login_count"] > 0) else 3
        dev = u["last_device"] or "Web Browser (Tamaweb WASM)"
        st = u["status"] or "active"
        strk = u["streak_days"] if (u["streak_days"] and u["streak_days"] > 0) else 2
        cur.execute("""
            UPDATE users
            SET created_at = ?, last_login_at = ?, last_active_at = ?, login_count = ?,
                last_device = ?, status = ?, streak_days = ?
            WHERE id = ?
        """, (c_at, l_at, l_at, l_cnt, dev, st, strk, u["id"]))

    conn.commit()
    conn.close()

    # Đồng bộ admin sang PostgreSQL nếu có
    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            pcur = pg_conn.cursor()
            pcur.execute("SELECT id FROM users WHERE username = 'admin'")
            if not pcur.fetchone():
                pcur.execute("""
                    INSERT INTO users (
                        username, password, password_hash, role, created_at,
                        status, is_online, last_login_at, last_active_at, login_count,
                        last_device, streak_days, last_streak_date
                    ) VALUES (%s, %s, %s, 'admin', %s, 'active', 1, %s, %s, 15, 'Admin Console (macOS / Web)', 12, %s)
                """, ("admin", "admin123", admin_pw_hash, now - 7 * 86400, now, now, today_str))
            else:
                pcur.execute("UPDATE users SET role = 'admin', status = 'active' WHERE username = 'admin'")
            pg_conn.commit()
            pcur.close()
            pg_conn.close()
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    # 3. Đồng bộ các bản lưu local_save_*.json có sẵn trong thư mục client/
    client_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client")
    if os.path.isdir(client_dir):
        for fname in sorted(os.listdir(client_dir)):
            if fname.startswith("local_save_") and fname.endswith(".json"):
                fpath = os.path.join(client_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        pdata = json.load(f)
                    uid = str(pdata.get("user_id") or fname[len("local_save_"):-5]).strip().lower()
                    if not uid or uid == "player_1":
                        continue
                    _ensure_synced_player(uid, pdata, now)
                except Exception:
                    pass

    # 4. Đảm bảo có tài khoản mẫu ở các trạng thái (Bị khoá, Không hoạt động, Online, Mới hôm nay) nếu DB mới khởi tạo
    _ensure_demo_variety(now)
    _sync_postgres_and_sqlite()


def _ensure_synced_player(uid: str, pet_data: Dict[str, Any], now: float):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (uid,))
    exists = cur.fetchone()
    if not exists:
        pw = "123456"
        pw_hash = hash_password(pw)
        cur.execute("""
            INSERT INTO users (
                username, password, password_hash, role, created_at,
                status, is_online, last_login_at, last_active_at, login_count,
                last_device, streak_days, last_streak_date
            ) VALUES (?, ?, ?, 'user', ?, 'active', 1, ?, ?, 5, 'Pygame Desktop (macOS)', 4, ?)
        """, (uid, pw, pw_hash, now - 3600, now - 300, now - 120, datetime.date.today().isoformat()))
        conn.commit()
    cur.execute("SELECT user_id FROM pets WHERE user_id = ?", (uid,))
    pet_exists = cur.fetchone()
    conn.close()
    if not pet_exists:
        pet_data["user_id"] = uid
        save_pet_data(pet_data)


def _ensure_demo_variety(now: float):
    """Đảm bảo có đầy đủ dữ liệu mẫu cho các bộ đếm (Bị khoá, Không hoạt động, Online, Hôm nay) nếu chưa có"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Kiểm tra xem đã có tài khoản bị khoá và không hoạt động chưa
    cur.execute("SELECT COUNT(*) as c FROM users WHERE status = 'locked'")
    locked_cnt = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM users WHERE status = 'inactive'")
    inactive_cnt = cur.fetchone()["c"]

    today_str = datetime.date.today().isoformat()

    if locked_cnt == 0:
        uname = "dark_tama99"
        cur.execute("SELECT id FROM users WHERE username = ?", (uname,))
        if not cur.fetchone():
            pw_hash = hash_password("123456")
            lock_until = now + 7 * 86400
            cur.execute("""
                INSERT INTO users (
                    username, password, password_hash, role, created_at,
                    status, is_online, last_login_at, last_active_at, login_count,
                    last_device, streak_days, last_streak_date,
                    lock_reason, locked_until, locked_by, locked_at, lock_duration_label
                ) VALUES (?, '123456', ?, 'user', ?, 'locked', 0, ?, ?, 8,
                          'Chrome 130 / Windows 11', 3, ?,
                          'Gian lận Coin & XP (Auto-Clicker)', ?, 'admin', ?, '7 Ngày')
            """, (uname, pw_hash, now - 5 * 86400, now - 86400, now - 86400, today_str, lock_until, now - 3600))
            cur.execute("""
                INSERT INTO account_lock_history (
                    user_id, action, reason, duration_label, locked_until, performed_by, created_at
                ) VALUES (?, 'KHOÁ TÀI KHOẢN', 'Gian lận Coin & XP (Auto-Clicker)', '7 Ngày', ?, 'admin', ?)
            """, (uname, lock_until, now - 3600))
            conn.commit()
            save_pet_data({
                "user_id": uname,
                "pet_name": "DARKTAMA",
                "stage": 3,
                "character_file": "resources/img/character/chara_82b.png",
                "level": 5,
                "exp": 480,
                "gold": 9999,
                "hunger": 40.0,
                "energy": 50.0,
                "hygiene": 45.0,
                "happiness": 30.0,
                "age_seconds": 640,
                "unlocked_characters": [
                    "resources/img/character/chara_1b.png",
                    "resources/img/character/chara_21b.png",
                    "resources/img/character/chara_82b.png",
                ],
            })

    if inactive_cnt == 0:
        uname = "sleepy_mame"
        cur.execute("SELECT id FROM users WHERE username = ?", (uname,))
        if not cur.fetchone():
            pw_hash = hash_password("123456")
            cur.execute("""
                INSERT INTO users (
                    username, password, password_hash, role, created_at,
                    status, is_online, last_login_at, last_active_at, login_count,
                    last_device, streak_days, last_streak_date
                ) VALUES (?, '123456', ?, 'user', ?, 'inactive', 0, ?, ?, 2,
                          'Safari / iPhone iOS 18', 1, '2026-10-15')
            """, (uname, pw_hash, now - 35 * 86400, now - 32 * 86400, now - 32 * 86400))
            conn.commit()
            save_pet_data({
                "user_id": uname,
                "pet_name": "MAMETCHI",
                "stage": 2,
                "character_file": "resources/img/character/chara_133b.png",
                "level": 2,
                "exp": 120,
                "gold": 210,
                "hunger": 60.0,
                "energy": 80.0,
                "hygiene": 70.0,
                "happiness": 65.0,
                "age_seconds": 180,
                "unlocked_characters": [
                    "resources/img/character/chara_1b.png",
                    "resources/img/character/chara_133b.png",
                ],
            })

    # Đảm bảo các tài khoản chưa có pet sẽ có dữ liệu pet mặc định để hiển thị đầy đủ 4 phần
    cur.execute("SELECT username FROM users")
    all_unames = [r["username"] for r in cur.fetchall()]
    for uname in all_unames:
        cur.execute("SELECT user_id FROM pets WHERE user_id = ?", (uname,))
        if not cur.fetchone():
            default_chars = ["resources/img/character/chara_1b.png"]
            if uname == "admin":
                default_chars = [
                    "resources/img/character/chara_1b.png",
                    "resources/img/character/chara_133b.png",
                    "resources/img/character/chara_136b.png",
                    "resources/img/character/chara_150b.png",
                    "resources/img/character/chara_152b.png",
                ]
            save_pet_data({
                "user_id": uname,
                "pet_name": uname.upper()[:10],
                "stage": 4 if uname == "admin" else 1,
                "character_file": "resources/img/character/chara_133b.png" if uname == "admin" else "resources/img/character/chara_1b.png",
                "level": 10 if uname == "admin" else 1,
                "exp": 1250 if uname == "admin" else 45,
                "gold": 5000 if uname == "admin" else 300,
                "hunger": 100.0,
                "energy": 100.0,
                "hygiene": 100.0,
                "happiness": 100.0,
                "age_seconds": 1200 if uname == "admin" else 60,
                "unlocked_characters": default_chars,
            })

    conn.close()


def _check_and_auto_expire_lock(user_row: Dict[str, Any]) -> Tuple[bool, str]:
    """Kiểm tra tài khoản có đang bị khoá không. Nếu đã hết thời hạn khoá thì tự động mở khoá."""
    status = str(user_row.get("status") or "active").lower()
    if status != "locked":
        return False, ""

    now = time.time()
    locked_until = float(user_row.get("locked_until") or 0)
    uname = user_row.get("username", "")

    if locked_until > 0 and now >= locked_until:
        # Tự động mở khoá khi hết hạn
        unlock_user_account(uname, performed_by="system (hết hạn)", reason="Tự động mở khoá khi hết thời hạn")
        return False, ""

    reason = user_row.get("lock_reason") or "Vi phạm quy định trò chơi"
    if locked_until > 0:
        until_str = format_timestamp(locked_until)
        return True, f"TÀI KHOẢN BỊ KHOÁ ĐẾN {until_str}! LÝ DO: {reason}"
    return True, f"TÀI KHOẢN ĐÃ BỊ KHOÁ VĨNH VIỄN! LÝ DO: {reason}"


def register_user(username: str, password: str, device: str = "Web Browser (Tamaweb WASM)") -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    uname = username.strip().lower()
    pwd = password.strip()
    if len(uname) < 3:
        return False, "TÀI KHOẢN TỐI THIỂU 3 KÝ TỰ!", None
    if len(pwd) < 3:
        return False, "MẬT KHẨU TỐI THIỂU 3 KÝ TỰ!", None

    now = time.time()
    today_str = datetime.date.today().isoformat()
    pw_hash = hash_password(pwd)
    role = "admin" if uname == "admin" else "user"

    # 1. Lưu vào PostgreSQL
    pg_conn = _get_pg_conn()
    pg_saved = False
    if pg_conn is not None:
        try:
            cur = pg_conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = %s", (uname,))
            if cur.fetchone():
                cur.close()
                pg_conn.close()
                return False, "TÀI KHOẢN ĐÃ TỒN TẠI!", None
            cur.execute("""
                INSERT INTO users (
                    username, password, password_hash, role, created_at,
                    status, is_online, last_login_at, last_active_at, login_count,
                    last_device, streak_days, last_streak_date
                ) VALUES (%s, %s, %s, %s, %s, 'active', 1, %s, %s, 1, %s, 1, %s)
            """, (uname, pwd, pw_hash, role, now, now, now, device, today_str))
            pg_conn.commit()
            cur.close()
            pg_conn.close()
            pg_saved = True
        except Exception as e:
            try:
                pg_conn.close()
            except Exception:
                pass
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                return False, "TÀI KHOẢN ĐÃ TỒN TẠI!", None

    # 2. Lưu đồng bộ vào SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (
                username, password, password_hash, role, created_at,
                status, is_online, last_login_at, last_active_at, login_count,
                last_device, streak_days, last_streak_date
            ) VALUES (?, ?, ?, ?, ?, 'active', 1, ?, ?, 1, ?, 1, ?)
        """, (uname, pwd, pw_hash, role, now, now, now, device, today_str))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        if not pg_saved:
            return False, "TÀI KHOẢN ĐÃ TỒN TẠI!", None
    conn.close()

    log_analytics(uname, "register", {"engine": "postgresql" if pg_saved else "sqlite", "device": device, "desc": "Đăng ký tài khoản mới"})
    return True, "ĐĂNG KÝ THÀNH CÔNG!", {
        "username": uname,
        "role": role,
        "status": "active",
        "database": "PostgreSQL" if pg_saved else "SQLite",
    }


def login_user(username: str, password: str, device: str = "Web Browser (Tamaweb WASM)") -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    uname = username.strip().lower()
    pwd = password.strip()
    if not uname or not pwd:
        return False, "NHẬP TÀI KHOẢN & MẬT KHẨU!", None

    now = time.time()
    today_str = datetime.date.today().isoformat()
    yesterday_str = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    # Đặc biệt: luôn đảm bảo admin / admin123 có thể đăng nhập vào trang quản trị
    if uname == "admin" and pwd == "admin123":
        _ensure_admin_exists(now, today_str)

    # Đọc user từ SQLite (hoặc PostgreSQL)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (uname,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        # Kiểm tra trên PostgreSQL nếu SQLite chưa có
        pg_conn = _get_pg_conn()
        if pg_conn is not None:
            try:
                cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("SELECT * FROM users WHERE username = %s", (uname,))
                pg_row = cur.fetchone()
                cur.close()
                pg_conn.close()
                if pg_row:
                    row_d = dict(pg_row)
                else:
                    return False, "TÀI KHOẢN CHƯA ĐĂNG KÝ!", None
            except Exception:
                return False, "TÀI KHOẢN CHƯA ĐĂNG KÝ!", None
        else:
            return False, "TÀI KHOẢN CHƯA ĐĂNG KÝ!", None
    else:
        row_d = dict(row)
        conn.close()

    # Kiểm tra mật khẩu
    if not verify_password(pwd, row_d.get("password_hash", ""), row_d.get("password", "")):
        return False, "SAI MẬT KHẨU!", None

    # Kiểm tra trạng thái khoá tài khoản (trừ tài khoản admin gốc)
    if uname != "admin":
        is_locked, lock_msg = _check_and_auto_expire_lock(row_d)
        if is_locked:
            log_analytics(uname, "login_blocked", {"reason": row_d.get("lock_reason", ""), "device": device, "desc": "Đăng nhập bị chặn do tài khoản đang bị khoá"})
            return False, lock_msg, None

    # Tính chuỗi ngày duy trì (streak_days)
    prev_streak = int(row_d.get("streak_days") or 1)
    last_date = str(row_d.get("last_streak_date") or "")
    if last_date == today_str:
        new_streak = max(1, prev_streak)
    elif last_date == yesterday_str:
        new_streak = prev_streak + 1
    else:
        new_streak = max(1, prev_streak) if last_date == "" else 1

    new_login_count = int(row_d.get("login_count") or 0) + 1
    role = "admin" if uname == "admin" else (row_d.get("role") or "user")
    new_status = "active" if row_d.get("status") == "inactive" else (row_d.get("status") or "active")

    # Cập nhật thông tin đăng nhập trên SQLite
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET is_online = 1,
            status = ?,
            role = ?,
            last_login_at = ?,
            last_active_at = ?,
            login_count = ?,
            last_device = ?,
            streak_days = ?,
            last_streak_date = ?
        WHERE username = ?
    """, (new_status, role, now, now, new_login_count, device, new_streak, today_str, uname))
    conn.commit()
    conn.close()

    # Cập nhật trên PostgreSQL
    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            pcur = pg_conn.cursor()
            pcur.execute("""
                UPDATE users
                SET is_online = 1,
                    status = %s,
                    role = %s,
                    last_login_at = %s,
                    last_active_at = %s,
                    login_count = %s,
                    last_device = %s,
                    streak_days = %s,
                    last_streak_date = %s
                WHERE username = %s
            """, (new_status, role, now, now, new_login_count, device, new_streak, today_str, uname))
            pg_conn.commit()
            pcur.close()
            pg_conn.close()
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    log_analytics(uname, "login", {
        "engine": "postgresql" if is_using_postgres() else "sqlite",
        "device": device,
        "desc": f"Đăng nhập thành công trên {device}",
    })
    return True, "ĐĂNG NHẬP THÀNH CÔNG!", {
        "id": row_d.get("id", 1),
        "username": uname,
        "role": role,
        "status": new_status,
        "database": "PostgreSQL" if is_using_postgres() else "SQLite",
    }


def _ensure_admin_exists(now: float, today_str: str):
    pw_hash = hash_password("admin123")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users (
                username, password, password_hash, role, created_at,
                status, is_online, last_login_at, last_active_at, login_count,
                last_device, streak_days, last_streak_date
            ) VALUES ('admin', 'admin123', ?, 'admin', ?, 'active', 1, ?, ?, 1, 'Admin Console (Web / Desktop)', 5, ?)
        """, (pw_hash, now, now, now, today_str))
    else:
        cur.execute("""
            UPDATE users SET password = 'admin123', password_hash = ?, role = 'admin', status = 'active'
            WHERE username = 'admin'
        """, (pw_hash,))
    conn.commit()
    conn.close()


def logout_user(username: str):
    uname = username.strip().lower()
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_online = 0, last_active_at = ? WHERE username = ?", (now, uname))
    conn.commit()
    conn.close()

    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            pcur = pg_conn.cursor()
            pcur.execute("UPDATE users SET is_online = 0, last_active_at = %s WHERE username = %s", (now, uname))
            pg_conn.commit()
            pcur.close()
            pg_conn.close()
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass
    log_analytics(uname, "logout", {"desc": "Đăng xuất khỏi trò chơi"})


def list_users() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# =============================================================================
# HỆ THỐNG QUẢN TRỊ TÀI KHOẢN DÀNH CHO ADMIN (4 PHẦN THÔNG TIN + THỐNG KÊ + CRUD + KHOÁ/MỞ KHOÁ)
# =============================================================================

def _build_rich_account_dict(user_row: Dict[str, Any], pet_map: Dict[str, Dict[str, Any]],
                             activity_map: Dict[str, List[Dict[str, Any]]],
                             lock_map: Dict[str, List[Dict[str, Any]]],
                             now: float) -> Dict[str, Any]:
    uname = str(user_row.get("username", "")).lower()
    uid = int(user_row.get("id") or 0)

    # Tự động kiểm tra hết hạn khoá
    status = str(user_row.get("status") or "active").lower()
    locked_until = float(user_row.get("locked_until") or 0)
    if status == "locked" and locked_until > 0 and now >= locked_until:
        status = "active"

    created_at = float(user_row.get("created_at") or now)
    last_login_at = float(user_row.get("last_login_at") or created_at)
    last_active_at = float(user_row.get("last_active_at") or last_login_at)
    login_count = int(user_row.get("login_count") or 1)
    last_device = str(user_row.get("last_device") or "Web Browser (Tamaweb WASM)")
    streak_days = int(user_row.get("streak_days") or 1)

    # Trạng thái online: đang có cờ is_online == 1 và không bị khoá
    is_online = bool(int(user_row.get("is_online") or 0) == 1 and status == "active")

    # Kiểm tra đăng ký hôm nay
    today_date = datetime.date.today()
    created_date = datetime.datetime.fromtimestamp(created_at).date() if created_at > 0 else today_date
    is_registered_today = (created_date == today_date)

    # Thông tin trò chơi (Phần 2) từ bảng pets
    p_row = pet_map.get(uname) or {}
    full_state = {}
    if p_row.get("full_state_json"):
        try:
            full_state = json.loads(p_row["full_state_json"])
        except Exception:
            full_state = {}

    level = int(p_row.get("level") or full_state.get("level") or 1)
    exp = int(p_row.get("exp") or full_state.get("exp") or 0)
    total_xp = (level - 1) * 100 + exp if exp < (level - 1) * 100 else exp
    gold = int(full_state.get("gold") if full_state.get("gold") is not None else 300)
    unlocked_chars = full_state.get("unlocked_characters") or [p_row.get("character_file") or "resources/img/character/chara_1b.png"]
    unlocked_count = int(full_state.get("unlocked_count_override") or len(unlocked_chars) or 1)
    pet_name = str(p_row.get("pet_name") or full_state.get("pet_name") or uname.upper()[:10])
    character_file = str(p_row.get("character_file") or full_state.get("character_file") or "resources/img/character/chara_1b.png")
    stage = int(p_row.get("stage") or full_state.get("stage") or 1)

    # Phần 3: Lịch sử hoạt động
    raw_acts = activity_map.get(uname, [])
    activity_history = []
    event_labels = {
        "register": "Đăng ký tài khoản mới",
        "login": "Đăng nhập vào hệ thống",
        "logout": "Đăng xuất tài khoản",
        "login_blocked": "Đăng nhập bị từ chối (Tài khoản khoá)",
        "minigame_end": "Hoàn thành Minigame nhận thưởng",
        "game_start": "Khởi động trò chơi Tamaweb",
        "pet_save": "Đồng bộ dữ liệu thú cưng lên Cloud",
        "admin_create": "Được tạo bởi Quản trị viên",
        "admin_update": "Quản trị viên cập nhật thông tin",
        "admin_lock": "Quản trị viên khoá tài khoản",
        "admin_unlock": "Quản trị viên mở khoá tài khoản",
    }
    for act in raw_acts[:15]:
        payload = {}
        try:
            payload = json.loads(act.get("payload_json") or "{}")
        except Exception:
            pass
        ev_name = act.get("event_name", "activity")
        desc = payload.get("desc") or event_labels.get(ev_name, f"Hoạt động: {ev_name}")
        if ev_name == "minigame_end" and "score" in payload:
            desc = f"Chơi Minigame đạt {payload['score']} điểm"
        activity_history.append({
            "id": act.get("id", 0),
            "event_name": ev_name,
            "description": desc,
            "device": payload.get("device") or last_device,
            "timestamp": act.get("created_at", 0),
            "time_str": format_timestamp(act.get("created_at", 0), include_seconds=True),
        })

    if not activity_history:
        activity_history.append({
            "id": 0,
            "event_name": "login",
            "description": f"Đăng nhập vào game ({last_device})",
            "device": last_device,
            "timestamp": last_login_at,
            "time_str": format_timestamp(last_login_at, include_seconds=True),
        })

    # Phần 4: Lịch sử xử lý khoá / mở khoá
    raw_locks = lock_map.get(uname, [])
    lock_history = []
    for lk in raw_locks:
        until_ts = float(lk.get("locked_until") or 0)
        until_str = "Vĩnh viễn" if (lk.get("action") == "KHOÁ TÀI KHOẢN" and until_ts <= 0) else (
            format_timestamp(until_ts) if until_ts > 0 else "--"
        )
        lock_history.append({
            "id": lk.get("id", 0),
            "action": lk.get("action", "KHOÁ TÀI KHOẢN"),
            "reason": lk.get("reason") or "Không có ghi chú",
            "duration_label": lk.get("duration_label") or "--",
            "locked_until": until_ts,
            "locked_until_str": until_str,
            "performed_by": lk.get("performed_by") or "admin",
            "timestamp": lk.get("created_at", 0),
            "time_str": format_timestamp(lk.get("created_at", 0), include_seconds=True),
        })

    status_vn = {
        "active": "Đang hoạt động",
        "locked": "Bị khoá",
        "inactive": "Không hoạt động",
    }.get(status, "Đang hoạt động")

    return {
        # Phần 1: Thông tin cá nhân
        "id": uid,
        "player_code": f"PLR-{uid:04d}",
        "username": uname,
        "password": user_row.get("password", ""),
        "role": user_row.get("role", "user"),
        "created_at": created_at,
        "created_at_str": format_timestamp(created_at),
        "status": status,
        "status_vn": status_vn,
        "is_online": is_online,
        "is_registered_today": is_registered_today,

        # Phần 2: Thông tin trò chơi
        "pet_name": pet_name,
        "stage": stage,
        "character_file": character_file,
        "level": level,
        "exp": exp,
        "total_xp": total_xp,
        "gold": gold,
        "unlocked_characters": unlocked_chars,
        "unlocked_count": unlocked_count,
        "streak_days": streak_days,

        # Phần 3: Hoạt động tài khoản
        "last_login_at": last_login_at,
        "last_login_str": format_timestamp(last_login_at, include_seconds=True),
        "last_active_at": last_active_at,
        "login_count": login_count,
        "last_device": last_device,
        "activity_history": activity_history,

        # Phần 4: Lịch sử xử lý & Trạng thái khoá hiện tại
        "lock_reason": user_row.get("lock_reason") or "",
        "locked_until": locked_until,
        "locked_until_str": (
            "Vĩnh viễn" if (status == "locked" and locked_until <= 0)
            else (format_timestamp(locked_until) if locked_until > 0 else "--")
        ),
        "locked_by": user_row.get("locked_by") or ("admin" if status == "locked" else ""),
        "locked_at": float(user_row.get("locked_at") or 0),
        "locked_at_str": format_timestamp(user_row.get("locked_at")) if user_row.get("locked_at") else "--",
        "lock_duration_label": user_row.get("lock_duration_label") or ("Vĩnh viễn" if status == "locked" else "--"),
        "lock_history": lock_history,
    }


def get_admin_dashboard_data() -> Dict[str, Any]:
    """Lấy toàn bộ thống kê 6 chỉ số tổng quan và danh sách chi tiết 4 phần của tất cả tài khoản"""
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM users ORDER BY id ASC")
    user_rows = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM pets")
    pet_map = {str(r["user_id"]).lower(): dict(r) for r in cur.fetchall()}

    cur.execute("SELECT * FROM analytics ORDER BY created_at DESC LIMIT 300")
    activity_map: Dict[str, List[Dict[str, Any]]] = {}
    for r in cur.fetchall():
        uid = str(r["user_id"] or "").lower()
        activity_map.setdefault(uid, []).append(dict(r))

    cur.execute("SELECT * FROM account_lock_history ORDER BY created_at DESC")
    lock_map: Dict[str, List[Dict[str, Any]]] = {}
    for r in cur.fetchall():
        uid = str(r["user_id"] or "").lower()
        lock_map.setdefault(uid, []).append(dict(r))

    conn.close()

    accounts = [
        _build_rich_account_dict(u, pet_map, activity_map, lock_map, now)
        for u in user_rows
    ]

    total_accounts = len(accounts)
    active_accounts = sum(1 for a in accounts if a["status"] == "active")
    new_today_accounts = sum(1 for a in accounts if a["is_registered_today"])
    locked_accounts = sum(1 for a in accounts if a["status"] == "locked")
    online_players = sum(1 for a in accounts if a["is_online"])
    inactive_accounts = sum(1 for a in accounts if a["status"] == "inactive")

    return {
        "status": "success",
        "database": "PostgreSQL (tamaweb_db)" if is_using_postgres() else "SQLite (tamaweb.db)",
        "stats": {
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "new_today_accounts": new_today_accounts,
            "locked_accounts": locked_accounts,
            "online_players": online_players,
            "inactive_accounts": inactive_accounts,
        },
        "accounts": accounts,
        "locked_list": [a for a in accounts if a["status"] == "locked"],
    }


def admin_create_account(payload: Dict[str, Any], performed_by: str = "admin") -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    uname = str(payload.get("username") or "").strip().lower()
    pwd = str(payload.get("password") or "123456").strip()
    role = str(payload.get("role") or "user").strip().lower()
    status = str(payload.get("status") or "active").strip().lower()
    device = str(payload.get("last_device") or "Web Browser (Tamaweb WASM)").strip()
    level = max(1, int(payload.get("level") or 1))
    total_xp = max(0, int(payload.get("total_xp") or 0))
    gold = max(0, int(payload.get("gold") if payload.get("gold") is not None else 300))
    unlocked_count = max(1, int(payload.get("unlocked_count") or 1))
    streak_days = max(1, int(payload.get("streak_days") or 1))

    if len(uname) < 3:
        return False, "TÊN TÀI KHOẢN PHẢI TỪ 3 KÝ TỰ!", None
    if len(pwd) < 3:
        return False, "MẬT KHẨU PHẢI TỪ 3 KÝ TỰ!", None

    now = time.time()
    today_str = datetime.date.today().isoformat()
    pw_hash = hash_password(pwd)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (uname,))
    if cur.fetchone():
        conn.close()
        return False, "TÀI KHOẢN ĐÃ TỒN TẠI!", None

    cur.execute("""
        INSERT INTO users (
            username, password, password_hash, role, created_at,
            status, is_online, last_login_at, last_active_at, login_count,
            last_device, streak_days, last_streak_date
        ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, 1, ?, ?, ?)
    """, (uname, pwd, pw_hash, role, now, status, now, now, device, streak_days, today_str))
    conn.commit()
    conn.close()

    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            pcur = pg_conn.cursor()
            pcur.execute("""
                INSERT INTO users (
                    username, password, password_hash, role, created_at,
                    status, is_online, last_login_at, last_active_at, login_count,
                    last_device, streak_days, last_streak_date
                ) VALUES (%s, %s, %s, %s, %s, %s, 0, %s, %s, 1, %s, %s, %s)
            """, (uname, pwd, pw_hash, role, now, status, now, now, device, streak_days, today_str))
            pg_conn.commit()
            pcur.close()
            pg_conn.close()
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    sample_pool = [
        "resources/img/character/chara_1b.png",
        "resources/img/character/chara_21b.png",
        "resources/img/character/chara_82b.png",
        "resources/img/character/chara_133b.png",
        "resources/img/character/chara_136b.png",
        "resources/img/character/chara_140b.png",
        "resources/img/character/chara_150b.png",
        "resources/img/character/chara_152b.png",
    ]
    unlocked_list = [sample_pool[i % len(sample_pool)] for i in range(min(unlocked_count, 32))]
    save_pet_data({
        "user_id": uname,
        "pet_name": str(payload.get("pet_name") or uname.upper()[:10]),
        "stage": min(4, max(1, (level // 3) + 1)),
        "character_file": unlocked_list[-1],
        "level": level,
        "exp": total_xp,
        "gold": gold,
        "hunger": 100.0,
        "energy": 100.0,
        "hygiene": 100.0,
        "happiness": 100.0,
        "age_seconds": level * 60,
        "unlocked_characters": unlocked_list,
        "unlocked_count_override": unlocked_count,
    })

    log_analytics(uname, "admin_create", {
        "performed_by": performed_by,
        "device": device,
        "desc": f"Tài khoản được tạo bởi Quản trị viên ({performed_by})",
    })
    return True, f"ĐÃ THÊM TÀI KHOẢN '{uname.upper()}'!", {"username": uname}


def admin_update_account(target_username: str, payload: Dict[str, Any], performed_by: str = "admin") -> Tuple[bool, str]:
    uname = target_username.strip().lower()
    now = time.time()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (uname,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "KHÔNG TÌM THẤY TÀI KHOẢN!"
    user_d = dict(row)

    new_pwd = str(payload.get("password") if payload.get("password") is not None else user_d["password"]).strip()
    if len(new_pwd) < 3:
        conn.close()
        return False, "MẬT KHẨU TỐI THIỂU 3 KÝ TỰ!"
    new_hash = hash_password(new_pwd) if new_pwd != user_d["password"] else user_d["password_hash"]

    new_role = str(payload.get("role") or user_d.get("role") or "user").strip().lower()
    if uname == "admin":
        new_role = "admin"
    new_status = str(payload.get("status") or user_d.get("status") or "active").strip().lower()
    if uname == "admin":
        new_status = "active"
    new_device = str(payload.get("last_device") or user_d.get("last_device") or "Web Browser (Tamaweb WASM)").strip()
    new_streak = max(1, int(payload.get("streak_days") if payload.get("streak_days") is not None else (user_d.get("streak_days") or 1)))
    new_login_count = max(0, int(payload.get("login_count") if payload.get("login_count") is not None else (user_d.get("login_count") or 1)))
    is_online = int(payload.get("is_online") if payload.get("is_online") is not None else (user_d.get("is_online") or 0))
    if new_status != "active":
        is_online = 0

    cur.execute("""
        UPDATE users
        SET password = ?, password_hash = ?, role = ?, status = ?,
            last_device = ?, streak_days = ?, login_count = ?, is_online = ?
        WHERE username = ?
    """, (new_pwd, new_hash, new_role, new_status, new_device, new_streak, new_login_count, is_online, uname))
    conn.commit()
    conn.close()

    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            pcur = pg_conn.cursor()
            pcur.execute("""
                UPDATE users
                SET password = %s, password_hash = %s, role = %s, status = %s,
                    last_device = %s, streak_days = %s, login_count = %s, is_online = %s
                WHERE username = %s
            """, (new_pwd, new_hash, new_role, new_status, new_device, new_streak, new_login_count, is_online, uname))
            pg_conn.commit()
            pcur.close()
            pg_conn.close()
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    # Cập nhật thông tin trò chơi (Phần 2)
    existing_pet = get_pet_data(uname) or {"user_id": uname, "pet_name": uname.upper()[:10]}
    if payload.get("level") is not None:
        existing_pet["level"] = max(1, int(payload["level"]))
    if payload.get("total_xp") is not None:
        existing_pet["exp"] = max(0, int(payload["total_xp"]))
    if payload.get("gold") is not None:
        existing_pet["gold"] = max(0, int(payload["gold"]))
    if payload.get("unlocked_count") is not None:
        uc = max(1, int(payload["unlocked_count"]))
        existing_pet["unlocked_count_override"] = uc
        sample_pool = [
            "resources/img/character/chara_1b.png",
            "resources/img/character/chara_21b.png",
            "resources/img/character/chara_82b.png",
            "resources/img/character/chara_133b.png",
            "resources/img/character/chara_136b.png",
            "resources/img/character/chara_140b.png",
            "resources/img/character/chara_150b.png",
            "resources/img/character/chara_152b.png",
        ]
        existing_pet["unlocked_characters"] = [sample_pool[i % len(sample_pool)] for i in range(min(uc, 32))]

    save_pet_data(existing_pet)
    log_analytics(uname, "admin_update", {
        "performed_by": performed_by,
        "desc": f"Quản trị viên ({performed_by}) cập nhật hồ sơ & chỉ số game",
    })
    return True, f"ĐÃ CẬP NHẬT TÀI KHOẢN '{uname.upper()}'!"


def admin_delete_account(target_username: str, performed_by: str = "admin") -> Tuple[bool, str]:
    uname = target_username.strip().lower()
    if uname == "admin":
        return False, "KHÔNG THỂ XOÁ TÀI KHOẢN QUẢN TRỊ VIÊN GỐC!"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (uname,))
    if not cur.fetchone():
        conn.close()
        return False, "KHÔNG TÌM THẤY TÀI KHOẢN!"

    cur.execute("DELETE FROM users WHERE username = ?", (uname,))
    cur.execute("DELETE FROM pets WHERE user_id = ?", (uname,))
    cur.execute("DELETE FROM leaderboard WHERE user_id = ?", (uname,))
    cur.execute("DELETE FROM account_lock_history WHERE user_id = ?", (uname,))
    conn.commit()
    conn.close()

    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            pcur = pg_conn.cursor()
            pcur.execute("DELETE FROM users WHERE username = %s", (uname,))
            pcur.execute("DELETE FROM pets WHERE user_id = %s", (uname,))
            pcur.execute("DELETE FROM leaderboard WHERE user_id = %s", (uname,))
            pcur.execute("DELETE FROM account_lock_history WHERE user_id = %s", (uname,))
            pg_conn.commit()
            pcur.close()
            pg_conn.close()
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    return True, f"ĐÃ XOÁ TÀI KHOẢN '{uname.upper()}'!"


def lock_user_account(
    target_username: str,
    reason: str,
    duration_key: str = "24h",
    performed_by: str = "admin",
) -> Tuple[bool, str]:
    uname = target_username.strip().lower()
    if uname == "admin":
        return False, "KHÔNG THỂ KHOÁ TÀI KHOẢN QUẢN TRỊ VIÊN!"

    clean_reason = (reason or "").strip() or "Vi phạm quy định trò chơi"
    now = time.time()
    dur_secs, dur_label = LOCK_DURATION_SECONDS.get(duration_key, (0, duration_key or "Vĩnh viễn"))
    locked_until = (now + dur_secs) if dur_secs > 0 else 0.0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (uname,))
    if not cur.fetchone():
        conn.close()
        return False, "KHÔNG TÌM THẤY TÀI KHOẢN!"

    cur.execute("""
        UPDATE users
        SET status = 'locked',
            is_online = 0,
            lock_reason = ?,
            locked_until = ?,
            locked_by = ?,
            locked_at = ?,
            lock_duration_label = ?
        WHERE username = ?
    """, (clean_reason, locked_until, performed_by, now, dur_label, uname))

    cur.execute("""
        INSERT INTO account_lock_history (
            user_id, action, reason, duration_label, locked_until, performed_by, created_at
        ) VALUES (?, 'KHOÁ TÀI KHOẢN', ?, ?, ?, ?, ?)
    """, (uname, clean_reason, dur_label, locked_until, performed_by, now))
    conn.commit()
    conn.close()

    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            pcur = pg_conn.cursor()
            pcur.execute("""
                UPDATE users
                SET status = 'locked',
                    is_online = 0,
                    lock_reason = %s,
                    locked_until = %s,
                    locked_by = %s,
                    locked_at = %s,
                    lock_duration_label = %s
                WHERE username = %s
            """, (clean_reason, locked_until, performed_by, now, dur_label, uname))
            pcur.execute("""
                INSERT INTO account_lock_history (
                    user_id, action, reason, duration_label, locked_until, performed_by, created_at
                ) VALUES (%s, 'KHOÁ TÀI KHOẢN', %s, %s, %s, %s, %s)
            """, (uname, clean_reason, dur_label, locked_until, performed_by, now))
            pg_conn.commit()
            pcur.close()
            pg_conn.close()
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    log_analytics(uname, "admin_lock", {
        "performed_by": performed_by,
        "reason": clean_reason,
        "duration": dur_label,
        "desc": f"Bị khoá tài khoản ({dur_label}) - Lý do: {clean_reason}",
    })
    return True, f"ĐÃ KHOÁ '{uname.upper()}' ({dur_label.upper()})!"


def unlock_user_account(
    target_username: str,
    performed_by: str = "admin",
    reason: str = "Quản trị viên mở khoá tài khoản",
) -> Tuple[bool, str]:
    uname = target_username.strip().lower()
    now = time.time()
    clean_reason = (reason or "").strip() or "Quản trị viên mở khoá tài khoản"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (uname,))
    if not cur.fetchone():
        conn.close()
        return False, "KHÔNG TÌM THẤY TÀI KHOẢN!"

    cur.execute("""
        UPDATE users
        SET status = 'active',
            lock_reason = '',
            locked_until = 0,
            locked_by = '',
            locked_at = 0,
            lock_duration_label = ''
        WHERE username = ?
    """, (uname,))

    cur.execute("""
        INSERT INTO account_lock_history (
            user_id, action, reason, duration_label, locked_until, performed_by, created_at
        ) VALUES (?, 'MỞ KHOÁ', ?, 'Đã mở khoá', 0, ?, ?)
    """, (uname, clean_reason, performed_by, now))
    conn.commit()
    conn.close()

    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            pcur = pg_conn.cursor()
            pcur.execute("""
                UPDATE users
                SET status = 'active',
                    lock_reason = '',
                    locked_until = 0,
                    locked_by = '',
                    locked_at = 0,
                    lock_duration_label = ''
                WHERE username = %s
            """, (uname,))
            pcur.execute("""
                INSERT INTO account_lock_history (
                    user_id, action, reason, duration_label, locked_until, performed_by, created_at
                ) VALUES (%s, 'MỞ KHOÁ', %s, 'Đã mở khoá', 0, %s, %s)
            """, (uname, clean_reason, performed_by, now))
            pg_conn.commit()
            pcur.close()
            pg_conn.close()
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    log_analytics(uname, "admin_unlock", {
        "performed_by": performed_by,
        "reason": clean_reason,
        "desc": f"Được mở khoá bởi {performed_by}",
    })
    return True, f"ĐÃ MỞ KHOÁ TÀI KHOẢN '{uname.upper()}'!"


def save_pet_data(data: Dict[str, Any]) -> bool:
    now = time.time()
    user_id = str(data.get("user_id", "guest_1")).strip().lower()
    pet_name = data.get("pet_name", user_id.upper()[:10])
    stage = int(data.get("stage", 1))
    character_file = data.get("character_file", "resources/img/character/chara_1b.png")
    level = int(data.get("level", 1))
    exp = int(data.get("exp", 0))
    hunger = float(data.get("hunger", 100.0))
    energy = float(data.get("energy", 100.0))
    hygiene = float(data.get("hygiene", 100.0))
    happiness = float(data.get("happiness", 100.0))
    age_seconds = int(data.get("age_seconds", 0))
    full_state_json = json.dumps(data, ensure_ascii=False)

    stage_names = ["Trứng", "Sơ sinh", "Ấu thơ", "Thiếu niên", "Trưởng thành", "Đặc biệt"]
    stage_name = stage_names[min(max(0, stage), len(stage_names) - 1)]
    gold = int(data.get("gold", 0))
    generation = int(data.get("generation", 1))
    score = level * 1000 + generation * 500 + gold + age_seconds

    # 1. Lưu trên PostgreSQL
    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            cur = pg_conn.cursor()
            cur.execute("""
            INSERT INTO pets (
                user_id, pet_name, stage, character_file, level, exp,
                hunger, energy, hygiene, happiness, age_seconds, full_state_json, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(user_id) DO UPDATE SET
                pet_name=EXCLUDED.pet_name,
                stage=EXCLUDED.stage,
                character_file=EXCLUDED.character_file,
                level=EXCLUDED.level,
                exp=EXCLUDED.exp,
                hunger=EXCLUDED.hunger,
                energy=EXCLUDED.energy,
                hygiene=EXCLUDED.hygiene,
                happiness=EXCLUDED.happiness,
                age_seconds=EXCLUDED.age_seconds,
                full_state_json=EXCLUDED.full_state_json,
                updated_at=EXCLUDED.updated_at
            """, (
                user_id, pet_name, stage, character_file, level, exp,
                hunger, energy, hygiene, happiness, age_seconds, full_state_json, now
            ))
            cur.execute("""
            INSERT INTO leaderboard (user_id, pet_name, stage_name, level, age_seconds, score, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(user_id) DO UPDATE SET
                pet_name=EXCLUDED.pet_name,
                stage_name=EXCLUDED.stage_name,
                level=EXCLUDED.level,
                age_seconds=EXCLUDED.age_seconds,
                score=EXCLUDED.score,
                updated_at=EXCLUDED.updated_at
            """, (user_id, pet_name, stage_name, level, age_seconds, score, now))
            pg_conn.commit()
            cur.close()
            pg_conn.close()
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    # 2. Lưu đồng bộ trên SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO pets (
        user_id, pet_name, stage, character_file, level, exp,
        hunger, energy, hygiene, happiness, age_seconds, full_state_json, updated_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        pet_name=excluded.pet_name,
        stage=excluded.stage,
        character_file=excluded.character_file,
        level=excluded.level,
        exp=excluded.exp,
        hunger=excluded.hunger,
        energy=excluded.energy,
        hygiene=excluded.hygiene,
        happiness=excluded.happiness,
        age_seconds=excluded.age_seconds,
        full_state_json=excluded.full_state_json,
        updated_at=excluded.updated_at
    """, (
        user_id, pet_name, stage, character_file, level, exp,
        hunger, energy, hygiene, happiness, age_seconds, full_state_json, now
    ))

    cursor.execute("""
    INSERT INTO leaderboard (user_id, pet_name, stage_name, level, age_seconds, score, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        pet_name=excluded.pet_name,
        stage_name=excluded.stage_name,
        level=excluded.level,
        age_seconds=excluded.age_seconds,
        score=excluded.score,
        updated_at=excluded.updated_at
    """, (user_id, pet_name, stage_name, level, age_seconds, score, now))

    cursor.execute("UPDATE users SET last_active_at = ? WHERE username = ?", (now, user_id))
    conn.commit()
    conn.close()
    return True


def get_pet_data(user_id: str) -> Optional[Dict[str, Any]]:
    uid = user_id.strip().lower()
    # 1. Đọc từ PostgreSQL trước
    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM pets WHERE user_id = %s", (uid,))
            row = cur.fetchone()
            cur.close()
            pg_conn.close()
            if row:
                row_dict = dict(row)
                raw_json = row_dict.get("full_state_json")
                if raw_json:
                    try:
                        full_data = json.loads(raw_json)
                        if isinstance(full_data, dict):
                            row_dict.update(full_data)
                    except Exception:
                        pass
                return row_dict
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    # 2. Đọc từ SQLite nếu chưa có
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pets WHERE user_id = ?", (uid,))
    row = cursor.fetchone()
    conn.close()
    if row:
        row_dict = dict(row)
        raw_json = row_dict.get("full_state_json")
        if raw_json:
            try:
                full_data = json.loads(raw_json)
                if isinstance(full_data, dict):
                    row_dict.update(full_data)
            except Exception:
                pass
        return row_dict
    return None


def get_top_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT user_id, pet_name, stage_name, level, age_seconds, score FROM leaderboard ORDER BY score DESC LIMIT %s",
                (limit,),
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            pg_conn.close()
            if rows:
                return rows
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, pet_name, stage_name, level, age_seconds, score FROM leaderboard ORDER BY score DESC LIMIT ?",
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_analytics(user_id: str, event_name: str, payload: Dict[str, Any]):
    now = time.time()
    payload_str = json.dumps(payload, ensure_ascii=False)
    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            cur = pg_conn.cursor()
            cur.execute(
                "INSERT INTO analytics (user_id, event_name, payload_json, created_at) VALUES (%s, %s, %s, %s)",
                (user_id, event_name, payload_str, now),
            )
            pg_conn.commit()
            cur.close()
            pg_conn.close()
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO analytics (user_id, event_name, payload_json, created_at) VALUES (?, ?, ?, ?)",
        (user_id, event_name, payload_str, now),
    )
    conn.commit()
    conn.close()
