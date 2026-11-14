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


def hash_password(password: str, salt: Optional[str] = None) -> str:
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str, stored_plain: str = "") -> bool:
    if stored_plain and hmac.compare_digest(password, stored_plain):
        return True
    try:
        if "$" not in stored_hash:
            return hmac.compare_digest(password, stored_hash)
        salt, _ = stored_hash.split("$", 1)
        return hmac.compare_digest(hash_password(password, salt), stored_hash)
    except Exception:
        return False


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

    # Thử kết nối vào database mặc định `postgres` để chạy CREATE DATABASE tamaweb_db
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
    # 1. Khởi tạo trên PostgreSQL (nếu PostgreSQL đang chạy)
    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        cur = pg_conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(64) UNIQUE NOT NULL,
            password TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role VARCHAR(20) DEFAULT 'user',
            created_at DOUBLE PRECISION
        )
        """)
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
        pg_conn.commit()
        cur.close()
        pg_conn.close()

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
        created_at REAL
    )
    """)

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

    conn.commit()
    conn.close()


def register_user(username: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    uname = username.strip().lower()
    pwd = password.strip()
    if len(uname) < 3:
        return False, "TÀI KHOẢN TỐI THIỂU 3 KÝ TỰ!", None
    if len(pwd) < 3:
        return False, "MẬT KHẨU TỐI THIỂU 3 KÝ TỰ!", None

    now = time.time()
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
            cur.execute(
                "INSERT INTO users (username, password, password_hash, role, created_at) VALUES (%s, %s, %s, %s, %s)",
                (uname, pwd, pw_hash, role, now),
            )
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
        cursor.execute(
            "INSERT INTO users (username, password, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (uname, pwd, pw_hash, role, now),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        if not pg_saved:
            return False, "TÀI KHOẢN ĐÃ TỒN TẠI!", None
    conn.close()

    log_analytics(uname, "register", {"engine": "postgresql" if pg_saved else "sqlite"})
    return True, "ĐĂNG KÝ THÀNH CÔNG!", {
        "username": uname,
        "role": role,
        "database": "PostgreSQL" if pg_saved else "SQLite",
    }


def login_user(username: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    uname = username.strip().lower()
    pwd = password.strip()
    if not uname or not pwd:
        return False, "NHẬP TÀI KHOẢN & MẬT KHẨU!", None

    # 1. Kiểm tra trên PostgreSQL trước
    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM users WHERE username = %s", (uname,))
            row = cur.fetchone()
            cur.close()
            pg_conn.close()
            if row:
                if verify_password(pwd, row.get("password_hash", ""), row.get("password", "")):
                    log_analytics(uname, "login", {"engine": "postgresql"})
                    return True, "ĐĂNG NHẬP THÀNH CÔNG!", {
                        "username": row["username"],
                        "role": row.get("role", "user"),
                        "database": "PostgreSQL",
                    }
                return False, "SAI MẬT KHẨU!", None
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    # 2. Kiểm tra trên SQLite nếu chưa có
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (uname,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return False, "TÀI KHOẢN CHƯA ĐĂNG KÝ!", None

    row_d = dict(row)
    if not verify_password(pwd, row_d.get("password_hash", ""), row_d.get("password", "")):
        return False, "SAI MẬT KHẨU!", None

    log_analytics(uname, "login", {"engine": "sqlite"})
    return True, "ĐĂNG NHẬP THÀNH CÔNG!", {
        "username": row_d["username"],
        "role": row_d.get("role", "user"),
        "database": "PostgreSQL" if is_using_postgres() else "SQLite",
    }


def list_users() -> List[Dict[str, Any]]:
    pg_conn = _get_pg_conn()
    if pg_conn is not None:
        try:
            cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT id, username, password, role, created_at FROM users ORDER BY id ASC")
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            pg_conn.close()
            return rows
        except Exception:
            try:
                pg_conn.close()
            except Exception:
                pass

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password, role, created_at FROM users ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


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
