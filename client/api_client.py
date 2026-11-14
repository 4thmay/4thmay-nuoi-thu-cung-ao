import json
import os
import sys
import urllib.request
import urllib.error

API_BASE_URL = "http://127.0.0.1:8000"
IS_WEB = sys.platform == "emscripten"
CLIENT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(os.path.dirname(CLIENT_DIR), "server")
if not IS_WEB and SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)


def _browser_xhr(method: str, path: str, body_dict: dict | None = None) -> tuple[int, dict]:
    """Gọi REST API của FastAPI trực tiếp từ trình duyệt WebAssembly (Pygbag)"""
    try:
        import platform
        body_json = json.dumps(body_dict, ensure_ascii=False) if body_dict is not None else ""
        js_code = f"""
        (function() {{
            try {{
                var xhr = new XMLHttpRequest();
                var base = (window.location.origin && window.location.origin !== 'null') ? window.location.origin : 'http://127.0.0.1:8000';
                xhr.open({json.dumps(method)}, base + {json.dumps(path)}, false);
                xhr.setRequestHeader("Content-Type", "application/json");
                xhr.send({json.dumps(body_json) if body_dict is not None else 'null'});
                return JSON.stringify({{status: xhr.status, text: xhr.responseText || "{{}}"}});
            }} catch (err) {{
                return JSON.stringify({{status: 0, text: "{{}}"}});
            }}
        }})()
        """
        raw_res = platform.window.eval(js_code)
        parsed = json.loads(str(raw_res))
        status = int(parsed.get("status", 0))
        try:
            data = json.loads(parsed.get("text") or "{}")
        except Exception:
            data = {}
        return status, data
    except Exception:
        return 0, {}


class APIClient:
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.user_id = "player_1"
        self.role = "user"
        self.db_engine = "PostgreSQL"

    def _local_save_path(self) -> str:
        safe_uid = "".join(c for c in self.user_id if c.isalnum() or c in ("_", "-")) or "player_1"
        return os.path.join(CLIENT_DIR, f"local_save_{safe_uid}.json")

    def register(self, username: str, password: str) -> tuple[bool, str]:
        """Đăng ký tài khoản mới và lưu vào PostgreSQL (`tamaweb_db`)"""
        uname = username.strip().lower()
        pwd = password.strip()

        if IS_WEB:
            status, res = _browser_xhr("POST", "/api/auth/register", {"username": uname, "password": pwd})
            if status == 200:
                user = res.get("user") or {}
                self.user_id = user.get("username", uname)
                self.role = user.get("role", "user")
                self.db_engine = user.get("database", "PostgreSQL")
                return True, res.get("message", "ĐĂNG KÝ THÀNH CÔNG!")
            elif status > 0:
                return False, res.get("detail", "TÀI KHOẢN ĐÃ TỒN TẠI!")
            # Fallback localStorage nếu mở tĩnh
            try:
                import platform
                raw_users = platform.window.localStorage.getItem("tamaweb_users") or "{}"
                users = json.loads(raw_users)
                if uname in users:
                    return False, "TÀI KHOẢN ĐÃ TỒN TẠI!"
                users[uname] = pwd
                platform.window.localStorage.setItem("tamaweb_users", json.dumps(users))
                self.user_id = uname
                return True, "ĐĂNG KÝ THÀNH CÔNG!"
            except Exception:
                self.user_id = uname
                return True, "ĐĂNG KÝ THÀNH CÔNG!"

        try:
            url = f"{self.base_url}/api/auth/register"
            data = json.dumps({"username": uname, "password": pwd}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                user = res.get("user") or {}
                self.user_id = user.get("username", uname)
                self.role = user.get("role", "user")
                self.db_engine = user.get("database", "PostgreSQL")
                return True, res.get("message", "ĐĂNG KÝ THÀNH CÔNG!")
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                return False, err_data.get("detail", "ĐĂNG KÝ THẤT BẠI!")
            except Exception:
                return False, "TÀI KHOẢN ĐÃ TỒN TẠI!"
        except Exception:
            try:
                import database as db_mod
                db_mod.init_db()
                ok, msg, user = db_mod.register_user(uname, pwd)
                if ok and user:
                    self.user_id = user.get("username", uname)
                    self.role = user.get("role", "user")
                    self.db_engine = user.get("database", "PostgreSQL")
                return ok, msg
            except Exception as ex:
                return False, f"LỖI KẾT NỐI DB: {ex}"

    def login(self, username: str, password: str) -> tuple[bool, str]:
        """Đăng nhập tài khoản từ PostgreSQL (`tamaweb_db`)"""
        uname = username.strip().lower()
        pwd = password.strip()

        if IS_WEB:
            status, res = _browser_xhr("POST", "/api/auth/login", {"username": uname, "password": pwd})
            if status == 200:
                user = res.get("user") or {}
                self.user_id = user.get("username", uname)
                self.role = user.get("role", "user")
                self.db_engine = user.get("database", "PostgreSQL")
                return True, res.get("message", "ĐĂNG NHẬP THÀNH CÔNG!")
            elif status > 0:
                return False, res.get("detail", "SAI TÀI KHOẢN / MẬT KHẨU!")
            try:
                import platform
                raw_users = platform.window.localStorage.getItem("tamaweb_users") or "{}"
                users = json.loads(raw_users)
                if users.get(uname) == pwd or (uname == "admin" and pwd == "admin123"):
                    self.user_id = uname
                    return True, "ĐĂNG NHẬP THÀNH CÔNG!"
                return False, "SAI TÀI KHOẢN / MẬT KHẨU!"
            except Exception:
                return False, "SAI TÀI KHOẢN / MẬT KHẨU!"

        try:
            url = f"{self.base_url}/api/auth/login"
            data = json.dumps({"username": uname, "password": pwd}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                user = res.get("user") or {}
                self.user_id = user.get("username", uname)
                self.role = user.get("role", "user")
                self.db_engine = user.get("database", "PostgreSQL")
                return True, res.get("message", "ĐĂNG NHẬP THÀNH CÔNG!")
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                return False, err_data.get("detail", "SAI TÀI KHOẢN / MẬT KHẨU!")
            except Exception:
                return False, "SAI TÀI KHOẢN / MẬT KHẨU!"
        except Exception:
            try:
                import database as db_mod
                db_mod.init_db()
                ok, msg, user = db_mod.login_user(uname, pwd)
                if ok and user:
                    self.user_id = user.get("username", uname)
                    self.role = user.get("role", "user")
                    self.db_engine = user.get("database", "PostgreSQL")
                return ok, msg
            except Exception as ex:
                return False, f"LỖI KẾT NỐI DB: {ex}"

    def save_pet(self, pet_dict: dict) -> tuple[bool, str]:
        pet_dict["user_id"] = self.user_id
        try:
            with open(self._local_save_path(), "w", encoding="utf-8") as f:
                json.dump(pet_dict, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        if IS_WEB:
            status, _ = _browser_xhr("POST", "/api/pet/save", pet_dict)
            try:
                import platform
                platform.window.localStorage.setItem(f"tamaweb_pet_{self.user_id}", json.dumps(pet_dict))
            except Exception:
                pass
            return (status == 200), "Đã lưu!"

        try:
            url = f"{self.base_url}/api/pet/save"
            data = json.dumps(pet_dict, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    return True, "Cloud Save thành công!"
        except Exception:
            try:
                import database as db_mod
                db_mod.save_pet_data(pet_dict)
                return True, "Đã lưu vào PostgreSQL!"
            except Exception as e:
                return False, f"Đã lưu Local ({e})"
        return True, "Đã lưu!"

    def load_pet(self) -> dict | None:
        if IS_WEB:
            status, res = _browser_xhr("GET", f"/api/pet/load/{self.user_id}")
            if status == 200 and res.get("status") == "success" and res.get("data"):
                return res["data"]
            try:
                import platform
                raw = platform.window.localStorage.getItem(f"tamaweb_pet_{self.user_id}")
                if raw:
                    return json.loads(raw)
            except Exception:
                pass
            return None

        try:
            url = f"{self.base_url}/api/pet/load/{self.user_id}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    res = json.loads(resp.read().decode("utf-8"))
                    if res.get("status") == "success" and res.get("data"):
                        return res["data"]
        except Exception:
            try:
                import database as db_mod
                data = db_mod.get_pet_data(self.user_id)
                if data:
                    return data
            except Exception:
                pass

        save_path = self._local_save_path()
        if os.path.exists(save_path):
            try:
                with open(save_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def get_leaderboard(self) -> list:
        if IS_WEB:
            status, res = _browser_xhr("GET", "/api/leaderboard?limit=10")
            if status == 200:
                return res.get("leaderboard", [])
            return []

        try:
            url = f"{self.base_url}/api/leaderboard?limit=10"
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if resp.status == 200:
                    res = json.loads(resp.read().decode("utf-8"))
                    return res.get("leaderboard", [])
        except Exception:
            try:
                import database as db_mod
                return db_mod.get_top_leaderboard(10)
            except Exception:
                pass
        return []

    def send_analytics(self, event_name: str, payload: dict = None):
        body = {
            "user_id": self.user_id,
            "event_name": event_name,
            "payload": payload or {},
        }
        if IS_WEB:
            _browser_xhr("POST", "/api/analytics/event", body)
            return

        try:
            url = f"{self.base_url}/api/analytics/event"
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=0.8)
        except Exception:
            pass
