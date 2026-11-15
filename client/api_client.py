import json
import os
import sys
import time
import urllib.request
import urllib.error

API_BASE_URL = "http://127.0.0.1:8000"
IS_WEB = sys.platform == "emscripten"
CLIENT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(os.path.dirname(CLIENT_DIR), "server")
if not IS_WEB and SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)


class APIClient:
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.user_id = "player_1"
        self.role = "user"
        self.db_engine = "PostgreSQL"
        self._desktop_auth_result = None
        self._init_web_bridge()

    def _init_web_bridge(self):
        """Khởi tạo cầu nối JavaScript không chặn (asynchronous non-blocking) cho trình duyệt"""
        if not IS_WEB:
            return
        try:
            import platform
            js_init = """
            (function() {
                if (!window.__tamaweb_api) {
                    window.__tamaweb_api = {
                        result: null,
                        in_flight: false,
                        leaderboard: [],
                        request: function(reqId, method, path, bodyJson) {
                            window.__tamaweb_api.in_flight = true;
                            window.__tamaweb_api.result = null;
                            var base = (window.location.origin && window.location.origin !== 'null') ? window.location.origin : 'http://127.0.0.1:8000';
                            var opts = {
                                method: method,
                                headers: {'Content-Type': 'application/json'}
                            };
                            if (bodyJson) {
                                opts.body = (typeof bodyJson === 'string') ? bodyJson : JSON.stringify(bodyJson);
                            }
                            fetch(base + path, opts)
                                .then(function(resp) {
                                    return resp.text().then(function(text) {
                                        var data = {};
                                        try { data = JSON.parse(text); } catch(e) { data = {detail: text}; }
                                        window.__tamaweb_api.result = {
                                            id: reqId,
                                            status: resp.status,
                                            ok: resp.ok,
                                            data: data
                                        };
                                        window.__tamaweb_api.in_flight = false;
                                    });
                                })
                                .catch(function(err) {
                                    window.__tamaweb_api.result = {
                                        id: reqId,
                                        status: 0,
                                        ok: false,
                                        data: {detail: 'Không thể kết nối tới máy chủ!'}
                                    };
                                    window.__tamaweb_api.in_flight = false;
                                });
                        },
                        fetchLeaderboard: function() {
                            var base = (window.location.origin && window.location.origin !== 'null') ? window.location.origin : 'http://127.0.0.1:8000';
                            fetch(base + '/api/leaderboard?limit=10')
                                .then(function(r) { return r.json(); })
                                .then(function(d) {
                                    if (d && d.leaderboard) {
                                        window.__tamaweb_api.leaderboard = d.leaderboard;
                                    }
                                })
                                .catch(function() {});
                        }
                    };
                    window.__tamaweb_api.fetchLeaderboard();
                }
            })();
            """
            platform.window.eval(js_init)
        except Exception as e:
            print("Init web bridge warning:", e)

    def _local_save_path(self) -> str:
        safe_uid = "".join(c for c in self.user_id if c.isalnum() or c in ("_", "-")) or "player_1"
        return os.path.join(CLIENT_DIR, f"local_save_{safe_uid}.json")

    # =========================================================================
    # XÁC THỰC BẤT ĐỒNG BỘ (KHÔNG BAO GIỜ GÂY ĐƠ TRÌNH DUYỆT)
    # =========================================================================
    def start_auth_request(self, mode: str, username: str, password: str) -> str:
        """Gửi yêu cầu đăng ký/đăng nhập bất đồng bộ qua fetch native của trình duyệt"""
        uname = username.strip().lower()
        pwd = password.strip()
        req_id = f"auth_{int(time.time() * 1000)}"
        path = "/api/auth/register" if mode == "register" else "/api/auth/login"
        payload = {"username": uname, "password": pwd}

        if IS_WEB:
            try:
                import platform
                body_json = json.dumps(payload, ensure_ascii=False)
                js = f"""
                (function() {{
                    if (!window.__tamaweb_api) {{
                        window.__tamaweb_api = {{
                            result: null,
                            in_flight: false,
                            leaderboard: [],
                            request: function(reqId, method, path, bodyJson) {{
                                window.__tamaweb_api.in_flight = true;
                                window.__tamaweb_api.result = null;
                                var base = (window.location.origin && window.location.origin !== 'null') ? window.location.origin : 'http://127.0.0.1:8000';
                                var opts = {{
                                    method: method,
                                    headers: {{'Content-Type': 'application/json'}}
                                }};
                                if (bodyJson) {{
                                    opts.body = (typeof bodyJson === 'string') ? bodyJson : JSON.stringify(bodyJson);
                                }}
                                fetch(base + path, opts)
                                    .then(function(resp) {{
                                        return resp.text().then(function(text) {{
                                            var data = {{}};
                                            try {{ data = JSON.parse(text); }} catch(e) {{ data = {{detail: text}}; }}
                                            window.__tamaweb_api.result = {{
                                                id: reqId,
                                                status: resp.status,
                                                ok: resp.ok,
                                                data: data
                                            }};
                                            window.__tamaweb_api.in_flight = false;
                                        }});
                                    }})
                                    .catch(function(err) {{
                                        window.__tamaweb_api.result = {{
                                            id: reqId,
                                            status: 0,
                                            ok: false,
                                            data: {{detail: 'Không thể kết nối tới máy chủ!'}}
                                        }};
                                        window.__tamaweb_api.in_flight = false;
                                    }});
                            }}
                        }};
                    }}
                    window.__tamaweb_api.request({json.dumps(req_id)}, 'POST', {json.dumps(path)}, {json.dumps(body_json)});
                }})();
                """
                platform.window.eval(js)
            except Exception as e:
                print("start_auth_request error:", e)
        else:
            # Trên Desktop thực hiện qua urllib đồng bộ
            if mode == "register":
                ok, msg = self.register(uname, pwd)
            else:
                ok, msg = self.login(uname, pwd)
            self._desktop_auth_result = {
                "id": req_id,
                "ok": ok,
                "status": 200 if ok else 400,
                "data": {
                    "user": {"username": self.user_id, "role": self.role, "database": self.db_engine},
                    "message": msg,
                    "detail": msg,
                    "pet_data": self.load_pet() if ok else None,
                },
            }
        return req_id

    def check_auth_response(self) -> dict | None:
        """Kiểm tra xem yêu cầu xác thực đã có kết quả trả về từ server chưa"""
        if IS_WEB:
            try:
                import platform
                raw = platform.window.eval("""
                (function() {
                    if (!window.__tamaweb_api || !window.__tamaweb_api.result) return "";
                    var r = window.__tamaweb_api.result;
                    window.__tamaweb_api.result = null;
                    return JSON.stringify(r);
                })()
                """)
                if raw:
                    return json.loads(str(raw))
            except Exception as e:
                print("check_auth_response error:", e)
            return None
        else:
            res = self._desktop_auth_result
            self._desktop_auth_result = None
            return res

    def get_cached_user(self, username: str) -> str | None:
        """Đọc mật khẩu đã lưu trong localStorage"""
        uname = username.strip().lower()
        if IS_WEB:
            try:
                import platform
                raw = platform.window.localStorage.getItem("tamaweb_users")
                if raw:
                    users = json.loads(str(raw))
                    return users.get(uname)
            except Exception:
                pass
        return None

    def cache_user(self, username: str, password: str):
        """Lưu thông tin đăng nhập vào localStorage để đăng nhập mượt mà"""
        uname = username.strip().lower()
        if IS_WEB:
            try:
                import platform
                raw = platform.window.localStorage.getItem("tamaweb_users") or "{}"
                users = json.loads(str(raw))
                users[uname] = password
                platform.window.localStorage.setItem("tamaweb_users", json.dumps(users, ensure_ascii=False))
            except Exception:
                pass

    # =========================================================================
    # CÁC HÀM XÁC THỰC ĐỒNG BỘ DỰ PHÒNG (DÙNG CHO DESKTOP)
    # =========================================================================
    def register(self, username: str, password: str) -> tuple[bool, str]:
        uname = username.strip().lower()
        pwd = password.strip()
        try:
            url = f"{self.base_url}/api/auth/register"
            data = json.dumps({"username": uname, "password": pwd}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                user = res.get("user") or {}
                self.user_id = user.get("username", uname)
                self.role = user.get("role", "user")
                self.db_engine = user.get("database", "PostgreSQL")
                return True, res.get("message", "ĐĂNG KÝ THÀNH CÔNG!")
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                detail = err_data.get("detail", "ĐĂNG KÝ THẤT BẠI!")
                return False, detail if isinstance(detail, str) else str(detail)
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
        uname = username.strip().lower()
        pwd = password.strip()
        try:
            url = f"{self.base_url}/api/auth/login"
            data = json.dumps({"username": uname, "password": pwd}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                user = res.get("user") or {}
                self.user_id = user.get("username", uname)
                self.role = user.get("role", "user")
                self.db_engine = user.get("database", "PostgreSQL")
                return True, res.get("message", "ĐĂNG NHẬP THÀNH CÔNG!")
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                detail = err_data.get("detail", "SAI TÀI KHOẢN / MẬT KHẨU!")
                return False, detail if isinstance(detail, str) else str(detail)
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

    # =========================================================================
    # LƯU VÀ TẢI THÚ CƯNG (TỨC THÌ LOCALSTORAGE + ĐỒNG BỘ NGẦM LÊN CLOUD)
    # =========================================================================
    def save_pet(self, pet_dict: dict) -> tuple[bool, str]:
        pet_dict["user_id"] = self.user_id

        if IS_WEB:
            try:
                import platform
                # 1. Lưu ngay vào localStorage (0ms, không lag, không mất)
                platform.window.localStorage.setItem(
                    f"tamaweb_pet_{self.user_id}", json.dumps(pet_dict, ensure_ascii=False)
                )
                # 2. Đồng bộ ngầm lên PostgreSQL qua fetch (non-blocking)
                body_json = json.dumps(pet_dict, ensure_ascii=False)
                js = f"""
                (function() {{
                    var base = (window.location.origin && window.location.origin !== 'null') ? window.location.origin : 'http://127.0.0.1:8000';
                    fetch(base + '/api/pet/save', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: {json.dumps(body_json)}
                    }}).catch(function(){{}});
                }})();
                """
                platform.window.eval(js)
            except Exception as e:
                print("save_pet web error:", e)
            return True, "Đã lưu!"

        # Trên Desktop
        try:
            with open(self._local_save_path(), "w", encoding="utf-8") as f:
                json.dump(pet_dict, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

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
            try:
                import platform
                raw = platform.window.localStorage.getItem(f"tamaweb_pet_{self.user_id}")
                if raw:
                    return json.loads(str(raw))
            except Exception:
                pass
            return None

        # Trên Desktop
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

    # =========================================================================
    # BẢNG XẾP HẠNG & ANALYTICS
    # =========================================================================
    def get_leaderboard(self) -> list:
        if IS_WEB:
            try:
                import platform
                raw = platform.window.eval("""
                (function() {
                    if (window.__tamaweb_api) {
                        if (window.__tamaweb_api.fetchLeaderboard) {
                            window.__tamaweb_api.fetchLeaderboard();
                        }
                        if (window.__tamaweb_api.leaderboard && window.__tamaweb_api.leaderboard.length > 0) {
                            return JSON.stringify(window.__tamaweb_api.leaderboard);
                        }
                    }
                    return "";
                })()
                """)
                if raw:
                    return json.loads(str(raw))
            except Exception:
                pass
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
            try:
                import platform
                body_json = json.dumps(body, ensure_ascii=False)
                js = f"""
                (function() {{
                    var base = (window.location.origin && window.location.origin !== 'null') ? window.location.origin : 'http://127.0.0.1:8000';
                    fetch(base + '/api/analytics/event', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: {json.dumps(body_json)}
                    }}).catch(function(){{}});
                }})();
                """
                platform.window.eval(js)
            except Exception:
                pass
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
            urllib.request.urlopen(req, timeout=1.0)
        except Exception:
            pass
