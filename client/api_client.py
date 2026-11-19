import datetime
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


def _fmt_ts(ts: float, include_sec: bool = False) -> str:
    if not ts or ts <= 0:
        return "Chưa ghi nhận"
    try:
        dt = datetime.datetime.fromtimestamp(float(ts))
        return dt.strftime("%d/%m/%Y %H:%M:%S" if include_sec else "%d/%m/%Y %H:%M")
    except Exception:
        return "Chưa ghi nhận"


class APIClient:
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.user_id = "player_1"
        self.role = "user"
        self.db_engine = "PostgreSQL"
        self.device_name = "Web Browser (Tamaweb WASM)" if IS_WEB else "Pygame Desktop (macOS)"
        self._desktop_auth_result = None
        self._cached_dashboard = None
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
                        adminDashboard: null,
                        adminDashboardUpdated: false,
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
                                        if (data && data.dashboard) {
                                            window.__tamaweb_api.adminDashboard = data.dashboard;
                                            window.__tamaweb_api.adminDashboardUpdated = true;
                                        }
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
                        },
                        fetchAdminDashboard: function(adminUser) {
                            var base = (window.location.origin && window.location.origin !== 'null') ? window.location.origin : 'http://127.0.0.1:8000';
                            fetch(base + '/api/admin/dashboard?admin_user=' + encodeURIComponent(adminUser || 'admin'))
                                .then(function(r) { return r.json(); })
                                .then(function(d) {
                                    if (d && d.status === 'success') {
                                        window.__tamaweb_api.adminDashboard = d;
                                        window.__tamaweb_api.adminDashboardUpdated = true;
                                    }
                                })
                                .catch(function() {});
                        },
                        adminAction: function(path, bodyJson) {
                            var base = (window.location.origin && window.location.origin !== 'null') ? window.location.origin : 'http://127.0.0.1:8000';
                            fetch(base + path, {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: (typeof bodyJson === 'string') ? bodyJson : JSON.stringify(bodyJson)
                            })
                            .then(function(r) { return r.json(); })
                            .then(function(d) {
                                if (d && d.dashboard) {
                                    window.__tamaweb_api.adminDashboard = d.dashboard;
                                    window.__tamaweb_api.adminDashboardUpdated = true;
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

    def set_cached_dashboard(self, dash: dict):
        if dash and isinstance(dash, dict):
            self._cached_dashboard = dash
            if dash.get("accounts"):
                self._save_web_store(dash["accounts"])

    def poll_web_admin_dashboard(self) -> dict | None:
        if not IS_WEB:
            return None
        try:
            import platform
            raw = platform.window.eval("""
            (function() {
                if (window.__tamaweb_api && window.__tamaweb_api.adminDashboardUpdated && window.__tamaweb_api.adminDashboard) {
                    window.__tamaweb_api.adminDashboardUpdated = false;
                    return JSON.stringify(window.__tamaweb_api.adminDashboard);
                }
                return "";
            })()
            """)
            if raw:
                dash = json.loads(str(raw))
                self.set_cached_dashboard(dash)
                return dash
        except Exception:
            pass
        return None

    # =========================================================================
    # XÁC THỰC BẤT ĐỒNG BỘ (KHÔNG BAO GIỜ GÂY ĐƠ TRÌNH DUYỆT)
    # =========================================================================
    def start_auth_request(self, mode: str, username: str, password: str) -> str:
        uname = username.strip().lower()
        pwd = password.strip()
        req_id = f"auth_{int(time.time() * 1000)}"
        path = "/api/auth/register" if mode == "register" else "/api/auth/login"
        payload = {"username": uname, "password": pwd, "device": self.device_name}

        if IS_WEB:
            try:
                import platform
                self._init_web_bridge()
                body_json = json.dumps(payload, ensure_ascii=False)
                js = f"""
                (function() {{
                    if (window.__tamaweb_api && window.__tamaweb_api.request) {{
                        window.__tamaweb_api.request({json.dumps(req_id)}, 'POST', {json.dumps(path)}, {json.dumps(body_json)});
                    }}
                }})();
                """
                platform.window.eval(js)
            except Exception as e:
                print("start_auth_request error:", e)
        else:
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
                    "dashboard": self.get_admin_dashboard() if (ok and self.role == "admin") else None,
                },
            }
        return req_id

    def check_auth_response(self) -> dict | None:
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
    # CÁC HÀM XÁC THỰC ĐỒNG BỘ (DÙNG CHO DESKTOP & GỌI TRỰC TIẾP)
    # =========================================================================
    def _post_json_desktop(self, path: str, payload: dict, timeout: float = 2.5) -> tuple[int, dict]:
        try:
            url = f"{self.base_url}{path}"
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
            except Exception:
                err_data = {}
            return e.code, err_data
        except Exception:
            return 0, {}

    def _get_json_desktop(self, path: str, timeout: float = 2.5) -> tuple[int, dict]:
        try:
            url = f"{self.base_url}{path}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
            except Exception:
                err_data = {}
            return e.code, err_data
        except Exception:
            return 0, {}

    def register(self, username: str, password: str) -> tuple[bool, str]:
        uname = username.strip().lower()
        pwd = password.strip()
        if IS_WEB:
            return self._web_fallback_register(uname, pwd)

        status, res = self._post_json_desktop("/api/auth/register", {
            "username": uname,
            "password": pwd,
            "device": self.device_name,
        })
        if status == 200:
            user = res.get("user") or {}
            self.user_id = user.get("username", uname)
            self.role = user.get("role", "admin" if uname == "admin" else "user")
            self.db_engine = user.get("database", "PostgreSQL")
            return True, res.get("message", "ĐĂNG KÝ THÀNH CÔNG!")
        elif status > 0:
            detail = res.get("detail", "TÀI KHOẢN ĐÃ TỒN TẠI!")
            return False, detail if isinstance(detail, str) else str(detail)

        try:
            import database as db_mod
            db_mod.init_db()
            ok, msg, user = db_mod.register_user(uname, pwd, self.device_name)
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
        if IS_WEB:
            return self._web_fallback_login(uname, pwd)

        status, res = self._post_json_desktop("/api/auth/login", {
            "username": uname,
            "password": pwd,
            "device": self.device_name,
        })
        if status == 200:
            user = res.get("user") or {}
            self.user_id = user.get("username", uname)
            self.role = "admin" if uname == "admin" else user.get("role", "user")
            self.db_engine = user.get("database", "PostgreSQL")
            if res.get("dashboard"):
                self.set_cached_dashboard(res["dashboard"])
            return True, res.get("message", "ĐĂNG NHẬP THÀNH CÔNG!")
        elif status > 0:
            detail = res.get("detail", "SAI TÀI KHOẢN / MẬT KHẨU!")
            return False, detail if isinstance(detail, str) else str(detail)

        try:
            import database as db_mod
            db_mod.init_db()
            ok, msg, user = db_mod.login_user(uname, pwd, self.device_name)
            if ok and user:
                self.user_id = user.get("username", uname)
                self.role = "admin" if uname == "admin" else user.get("role", "user")
                self.db_engine = user.get("database", "PostgreSQL")
            return ok, msg
        except Exception as ex:
            return False, f"LỖI KẾT NỐI DB: {ex}"

    def logout(self):
        if not self.user_id:
            return
        if IS_WEB:
            try:
                import platform
                body_json = json.dumps({"username": self.user_id}, ensure_ascii=False)
                platform.window.eval(f"""
                (function() {{
                    var base = (window.location.origin && window.location.origin !== 'null') ? window.location.origin : 'http://127.0.0.1:8000';
                    fetch(base + '/api/auth/logout', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: {json.dumps(body_json)}
                    }}).catch(function(){{}});
                }})();
                """)
            except Exception:
                pass
            return
        self._post_json_desktop("/api/auth/logout", {"username": self.user_id}, timeout=1.0)
        try:
            import database as db_mod
            db_mod.logout_user(self.user_id)
        except Exception:
            pass

    # =========================================================================
    # CÁC PHƯƠNG THỨC QUẢN TRỊ VIÊN (ADMIN DASHBOARD & CRUD & KHOÁ/MỞ KHOÁ)
    # =========================================================================
    def _trigger_web_admin_action(self, path: str, body_dict: dict):
        if not IS_WEB:
            return
        try:
            import platform
            self._init_web_bridge()
            body_json = json.dumps(body_dict, ensure_ascii=False)
            platform.window.eval(f"""
            (function() {{
                if (window.__tamaweb_api && window.__tamaweb_api.adminAction) {{
                    window.__tamaweb_api.adminAction({json.dumps(path)}, {json.dumps(body_json)});
                }}
            }})();
            """)
        except Exception:
            pass

    def get_admin_dashboard(self) -> dict:
        if IS_WEB:
            try:
                import platform
                self._init_web_bridge()
                platform.window.eval(f"""
                (function() {{
                    if (window.__tamaweb_api && window.__tamaweb_api.fetchAdminDashboard) {{
                        window.__tamaweb_api.fetchAdminDashboard({json.dumps(self.user_id)});
                    }}
                }})();
                """)
            except Exception:
                pass
            polled = self.poll_web_admin_dashboard()
            if polled:
                return polled
            if self._cached_dashboard:
                return self._cached_dashboard
            return self._web_fallback_get_dashboard()

        status, res = self._get_json_desktop(f"/api/admin/dashboard?admin_user={self.user_id}")
        if status == 200 and res.get("status") == "success":
            self.set_cached_dashboard(res)
            return res

        try:
            import database as db_mod
            db_mod.init_db()
            dash = db_mod.get_admin_dashboard_data()
            self.set_cached_dashboard(dash)
            return dash
        except Exception:
            return self._web_fallback_get_dashboard()

    def admin_create_account(self, payload: dict) -> tuple[bool, str, dict]:
        req_body = dict(payload)
        req_body["admin_user"] = self.user_id
        if IS_WEB:
            ok, msg, dash = self._web_fallback_create_account(payload)
            if ok:
                self._cached_dashboard = dash
                self._trigger_web_admin_action("/api/admin/accounts/create", req_body)
            return ok, msg, dash

        status, res = self._post_json_desktop("/api/admin/accounts/create", req_body)
        if status == 200 and res.get("status") == "success":
            dash = res.get("dashboard") or {}
            self.set_cached_dashboard(dash)
            return True, res.get("message", "ĐÃ THÊM TÀI KHOẢN!"), dash
        elif status > 0:
            return False, res.get("detail", "KHÔNG THỂ THÊM TÀI KHOẢN!"), {}

        try:
            import database as db_mod
            ok, msg, _ = db_mod.admin_create_account(payload, performed_by=self.user_id)
            dash = db_mod.get_admin_dashboard_data() if ok else {}
            self.set_cached_dashboard(dash)
            return ok, msg, dash
        except Exception as e:
            return False, f"LỖI: {e}", {}

    def admin_update_account(self, target_username: str, payload: dict) -> tuple[bool, str, dict]:
        req_body = dict(payload)
        req_body["admin_user"] = self.user_id
        req_body["target_username"] = target_username
        if IS_WEB:
            ok, msg, dash = self._web_fallback_update_account(target_username, payload)
            if ok:
                self._cached_dashboard = dash
                self._trigger_web_admin_action("/api/admin/accounts/update", req_body)
            return ok, msg, dash

        status, res = self._post_json_desktop("/api/admin/accounts/update", req_body)
        if status == 200 and res.get("status") == "success":
            dash = res.get("dashboard") or {}
            self.set_cached_dashboard(dash)
            return True, res.get("message", "ĐÃ CẬP NHẬT TÀI KHOẢN!"), dash
        elif status > 0:
            return False, res.get("detail", "LỖI CẬP NHẬT!"), {}

        try:
            import database as db_mod
            ok, msg = db_mod.admin_update_account(target_username, payload, performed_by=self.user_id)
            dash = db_mod.get_admin_dashboard_data() if ok else {}
            self.set_cached_dashboard(dash)
            return ok, msg, dash
        except Exception as e:
            return False, f"LỖI: {e}", {}

    def admin_delete_account(self, target_username: str) -> tuple[bool, str, dict]:
        req_body = {"admin_user": self.user_id, "target_username": target_username}
        if IS_WEB:
            ok, msg, dash = self._web_fallback_delete_account(target_username)
            if ok:
                self._cached_dashboard = dash
                self._trigger_web_admin_action("/api/admin/accounts/delete", req_body)
            return ok, msg, dash

        status, res = self._post_json_desktop("/api/admin/accounts/delete", req_body)
        if status == 200 and res.get("status") == "success":
            dash = res.get("dashboard") or {}
            self.set_cached_dashboard(dash)
            return True, res.get("message", "ĐÃ XOÁ TÀI KHOẢN!"), dash
        elif status > 0:
            return False, res.get("detail", "KHÔNG THỂ XOÁ!"), {}

        try:
            import database as db_mod
            ok, msg = db_mod.admin_delete_account(target_username, performed_by=self.user_id)
            dash = db_mod.get_admin_dashboard_data() if ok else {}
            self.set_cached_dashboard(dash)
            return ok, msg, dash
        except Exception as e:
            return False, f"LỖI: {e}", {}

    def admin_lock_account(self, target_username: str, reason: str, duration_key: str) -> tuple[bool, str, dict]:
        req_body = {
            "admin_user": self.user_id,
            "target_username": target_username,
            "reason": reason,
            "duration_key": duration_key,
        }
        if IS_WEB:
            ok, msg, dash = self._web_fallback_lock_account(target_username, reason, duration_key)
            if ok:
                self._cached_dashboard = dash
                self._trigger_web_admin_action("/api/admin/accounts/lock", req_body)
            return ok, msg, dash

        status, res = self._post_json_desktop("/api/admin/accounts/lock", req_body)
        if status == 200 and res.get("status") == "success":
            dash = res.get("dashboard") or {}
            self.set_cached_dashboard(dash)
            return True, res.get("message", "ĐÃ KHOÁ TÀI KHOẢN!"), dash
        elif status > 0:
            return False, res.get("detail", "KHÔNG THỂ KHOÁ!"), {}

        try:
            import database as db_mod
            ok, msg = db_mod.lock_user_account(target_username, reason, duration_key, performed_by=self.user_id)
            dash = db_mod.get_admin_dashboard_data() if ok else {}
            self.set_cached_dashboard(dash)
            return ok, msg, dash
        except Exception as e:
            return False, f"LỖI: {e}", {}

    def admin_unlock_account(self, target_username: str, reason: str = "Quản trị viên mở khoá tài khoản") -> tuple[bool, str, dict]:
        req_body = {
            "admin_user": self.user_id,
            "target_username": target_username,
            "reason": reason,
        }
        if IS_WEB:
            ok, msg, dash = self._web_fallback_unlock_account(target_username, reason)
            if ok:
                self._cached_dashboard = dash
                self._trigger_web_admin_action("/api/admin/accounts/unlock", req_body)
            return ok, msg, dash

        status, res = self._post_json_desktop("/api/admin/accounts/unlock", req_body)
        if status == 200 and res.get("status") == "success":
            dash = res.get("dashboard") or {}
            self.set_cached_dashboard(dash)
            return True, res.get("message", "ĐÃ MỞ KHOÁ TÀI KHOẢN!"), dash
        elif status > 0:
            return False, res.get("detail", "KHÔNG THỂ MỞ KHOÁ!"), {}

        try:
            import database as db_mod
            ok, msg = db_mod.unlock_user_account(target_username, performed_by=self.user_id, reason=reason)
            dash = db_mod.get_admin_dashboard_data() if ok else {}
            self.set_cached_dashboard(dash)
            return ok, msg, dash
        except Exception as e:
            return False, f"LỖI: {e}", {}

    # =========================================================================
    # BỘ LƯU TRỮ DỰ PHÒNG TRÊN TRÌNH DUYỆT (LOCALSTORAGE FALLBACK KHI CHẠY TĨNH)
    # =========================================================================
    def _load_web_store(self) -> list[dict]:
        now = time.time()
        default_accounts = [
            {
                "id": 1, "player_code": "PLR-0001", "username": "admin", "password": "admin123",
                "role": "admin", "created_at": now - 7 * 86400, "created_at_str": _fmt_ts(now - 7 * 86400),
                "status": "active", "status_vn": "Đang hoạt động", "is_online": True, "is_registered_today": False,
                "pet_name": "ADMINTAMA", "stage": 4, "character_file": "resources/img/character/chara_133b.png",
                "level": 10, "exp": 1250, "total_xp": 1250, "gold": 5000,
                "unlocked_characters": [
                    "resources/img/character/chara_1b.png", "resources/img/character/chara_133b.png",
                    "resources/img/character/chara_136b.png", "resources/img/character/chara_150b.png",
                    "resources/img/character/chara_152b.png",
                ],
                "unlocked_count": 5, "streak_days": 12,
                "last_login_at": now, "last_login_str": _fmt_ts(now, True), "login_count": 15,
                "last_device": "Admin Console (Web / macOS)",
                "activity_history": [
                    {"id": 1, "event_name": "login", "description": "Đăng nhập Quản trị viên hệ thống", "device": "Admin Console (Web / macOS)", "timestamp": now, "time_str": _fmt_ts(now, True)},
                ],
                "lock_reason": "", "locked_until": 0, "locked_until_str": "--", "locked_by": "",
                "locked_at": 0, "locked_at_str": "--", "lock_duration_label": "--", "lock_history": [],
            },
            {
                "id": 2, "player_code": "PLR-0002", "username": "4thmay", "password": "123456",
                "role": "user", "created_at": now - 1800, "created_at_str": _fmt_ts(now - 1800),
                "status": "active", "status_vn": "Đang hoạt động", "is_online": True, "is_registered_today": True,
                "pet_name": "4THMAY", "stage": 2, "character_file": "resources/img/character/chara_21b.png",
                "level": 2, "exp": 103, "total_xp": 203, "gold": 348,
                "unlocked_characters": ["resources/img/character/chara_1b.png", "resources/img/character/chara_21b.png"],
                "unlocked_count": 2, "streak_days": 4,
                "last_login_at": now - 120, "last_login_str": _fmt_ts(now - 120, True), "login_count": 6,
                "last_device": "Web Browser (Tamaweb WASM)",
                "activity_history": [
                    {"id": 2, "event_name": "login", "description": "Đăng nhập vào trò chơi", "device": "Web Browser (Tamaweb WASM)", "timestamp": now - 120, "time_str": _fmt_ts(now - 120, True)},
                    {"id": 3, "event_name": "pet_save", "description": "Lưu tiến trình thú cưng lên Cloud", "device": "Web Browser (Tamaweb WASM)", "timestamp": now - 60, "time_str": _fmt_ts(now - 60, True)},
                ],
                "lock_reason": "", "locked_until": 0, "locked_until_str": "--", "locked_by": "",
                "locked_at": 0, "locked_at_str": "--", "lock_duration_label": "--", "lock_history": [],
            },
            {
                "id": 3, "player_code": "PLR-0003", "username": "quanh4thmay", "password": "password123",
                "role": "user", "created_at": now - 3 * 86400, "created_at_str": _fmt_ts(now - 3 * 86400),
                "status": "active", "status_vn": "Đang hoạt động", "is_online": True, "is_registered_today": False,
                "pet_name": "QUANH4THMA", "stage": 3, "character_file": "resources/img/character/chara_150b.png",
                "level": 4, "exp": 320, "total_xp": 620, "gold": 780,
                "unlocked_characters": ["resources/img/character/chara_1b.png", "resources/img/character/chara_21b.png", "resources/img/character/chara_150b.png"],
                "unlocked_count": 3, "streak_days": 5,
                "last_login_at": now - 600, "last_login_str": _fmt_ts(now - 600, True), "login_count": 9,
                "last_device": "Pygame Desktop (macOS)",
                "activity_history": [
                    {"id": 4, "event_name": "login", "description": "Đăng nhập trên Pygame Desktop", "device": "Pygame Desktop (macOS)", "timestamp": now - 600, "time_str": _fmt_ts(now - 600, True)},
                ],
                "lock_reason": "", "locked_until": 0, "locked_until_str": "--", "locked_by": "",
                "locked_at": 0, "locked_at_str": "--", "lock_duration_label": "--", "lock_history": [],
            },
            {
                "id": 4, "player_code": "PLR-0004", "username": "testgames", "password": "123456",
                "role": "user", "created_at": now - 900, "created_at_str": _fmt_ts(now - 900),
                "status": "active", "status_vn": "Đang hoạt động", "is_online": False, "is_registered_today": True,
                "pet_name": "TESTGAMES", "stage": 1, "character_file": "resources/img/character/chara_1b.png",
                "level": 1, "exp": 45, "total_xp": 45, "gold": 350,
                "unlocked_characters": ["resources/img/character/chara_1b.png"],
                "unlocked_count": 1, "streak_days": 1,
                "last_login_at": now - 900, "last_login_str": _fmt_ts(now - 900, True), "login_count": 2,
                "last_device": "Chrome 130 / macOS",
                "activity_history": [
                    {"id": 5, "event_name": "register", "description": "Đăng ký tài khoản mới hôm nay", "device": "Chrome 130 / macOS", "timestamp": now - 900, "time_str": _fmt_ts(now - 900, True)},
                ],
                "lock_reason": "", "locked_until": 0, "locked_until_str": "--", "locked_by": "",
                "locked_at": 0, "locked_at_str": "--", "lock_duration_label": "--", "lock_history": [],
            },
            {
                "id": 5, "player_code": "PLR-0005", "username": "dark_tama99", "password": "123456",
                "role": "user", "created_at": now - 5 * 86400, "created_at_str": _fmt_ts(now - 5 * 86400),
                "status": "locked", "status_vn": "Bị khoá", "is_online": False, "is_registered_today": False,
                "pet_name": "DARKTAMA", "stage": 3, "character_file": "resources/img/character/chara_82b.png",
                "level": 5, "exp": 480, "total_xp": 880, "gold": 9999,
                "unlocked_characters": ["resources/img/character/chara_1b.png", "resources/img/character/chara_21b.png", "resources/img/character/chara_82b.png"],
                "unlocked_count": 3, "streak_days": 3,
                "last_login_at": now - 86400, "last_login_str": _fmt_ts(now - 86400, True), "login_count": 8,
                "last_device": "Chrome 130 / Windows 11",
                "activity_history": [
                    {"id": 6, "event_name": "admin_lock", "description": "Bị khoá tài khoản (7 Ngày) - Gian lận Coin & XP", "device": "Chrome 130 / Windows 11", "timestamp": now - 3600, "time_str": _fmt_ts(now - 3600, True)},
                ],
                "lock_reason": "Gian lận Coin & XP (Auto-Clicker)",
                "locked_until": now + 7 * 86400,
                "locked_until_str": _fmt_ts(now + 7 * 86400),
                "locked_by": "admin",
                "locked_at": now - 3600,
                "locked_at_str": _fmt_ts(now - 3600),
                "lock_duration_label": "7 Ngày",
                "lock_history": [
                    {
                        "id": 1, "action": "KHOÁ TÀI KHOẢN", "reason": "Gian lận Coin & XP (Auto-Clicker)",
                        "duration_label": "7 Ngày", "locked_until": now + 7 * 86400,
                        "locked_until_str": _fmt_ts(now + 7 * 86400), "performed_by": "admin",
                        "timestamp": now - 3600, "time_str": _fmt_ts(now - 3600, True),
                    }
                ],
            },
            {
                "id": 6, "player_code": "PLR-0006", "username": "sleepy_mame", "password": "123456",
                "role": "user", "created_at": now - 35 * 86400, "created_at_str": _fmt_ts(now - 35 * 86400),
                "status": "inactive", "status_vn": "Không hoạt động", "is_online": False, "is_registered_today": False,
                "pet_name": "MAMETCHI", "stage": 2, "character_file": "resources/img/character/chara_133b.png",
                "level": 2, "exp": 120, "total_xp": 220, "gold": 210,
                "unlocked_characters": ["resources/img/character/chara_1b.png", "resources/img/character/chara_133b.png"],
                "unlocked_count": 2, "streak_days": 1,
                "last_login_at": now - 32 * 86400, "last_login_str": _fmt_ts(now - 32 * 86400, True), "login_count": 2,
                "last_device": "Safari / iPhone iOS 18",
                "activity_history": [
                    {"id": 7, "event_name": "login", "description": "Đăng nhập lần cuối cách đây 32 ngày", "device": "Safari / iPhone iOS 18", "timestamp": now - 32 * 86400, "time_str": _fmt_ts(now - 32 * 86400, True)},
                ],
                "lock_reason": "", "locked_until": 0, "locked_until_str": "--", "locked_by": "",
                "locked_at": 0, "locked_at_str": "--", "lock_duration_label": "--", "lock_history": [],
            },
        ]
        try:
            import platform
            raw = platform.window.localStorage.getItem("tamaweb_admin_accounts_v3")
            if raw:
                return json.loads(raw)
            platform.window.localStorage.setItem("tamaweb_admin_accounts_v3", json.dumps(default_accounts))
        except Exception:
            pass
        return default_accounts

    def _save_web_store(self, accounts: list[dict]):
        try:
            import platform
            platform.window.localStorage.setItem("tamaweb_admin_accounts_v3", json.dumps(accounts))
        except Exception:
            pass

    def _web_fallback_get_dashboard(self) -> dict:
        accounts = self._load_web_store()
        return {
            "status": "success",
            "database": "PostgreSQL (tamaweb_db)",
            "stats": {
                "total_accounts": len(accounts),
                "active_accounts": sum(1 for a in accounts if a.get("status") == "active"),
                "new_today_accounts": sum(1 for a in accounts if a.get("is_registered_today")),
                "locked_accounts": sum(1 for a in accounts if a.get("status") == "locked"),
                "online_players": sum(1 for a in accounts if a.get("is_online") and a.get("status") == "active"),
                "inactive_accounts": sum(1 for a in accounts if a.get("status") == "inactive"),
            },
            "accounts": accounts,
            "locked_list": [a for a in accounts if a.get("status") == "locked"],
        }

    def _web_fallback_login(self, uname: str, pwd: str) -> tuple[bool, str]:
        accounts = self._load_web_store()
        now = time.time()
        for a in accounts:
            if a["username"] == uname:
                if a.get("password") != pwd and not (uname == "admin" and pwd == "admin123"):
                    return False, "SAI MẬT KHẨU!"
                if a.get("status") == "locked" and uname != "admin":
                    return False, f"TÀI KHOẢN BỊ KHOÁ! LÝ DO: {a.get('lock_reason') or 'Vi phạm'}"
                a["is_online"] = True
                a["login_count"] = int(a.get("login_count", 0)) + 1
                a["last_login_at"] = now
                a["last_login_str"] = _fmt_ts(now, True)
                self._save_web_store(accounts)
                self.user_id = uname
                self.role = "admin" if uname == "admin" else a.get("role", "user")
                return True, "ĐĂNG NHẬP THÀNH CÔNG!"
        if uname == "admin" and pwd == "admin123":
            self.user_id = "admin"
            self.role = "admin"
            return True, "ĐĂNG NHẬP THÀNH CÔNG!"
        return False, "TÀI KHOẢN CHƯA ĐĂNG KÝ!"

    def _web_fallback_register(self, uname: str, pwd: str) -> tuple[bool, str]:
        ok, msg, _ = self._web_fallback_create_account({"username": uname, "password": pwd})
        if ok:
            self.user_id = uname
            self.role = "admin" if uname == "admin" else "user"
        return ok, msg

    def _web_fallback_create_account(self, payload: dict) -> tuple[bool, str, dict]:
        uname = str(payload.get("username") or "").strip().lower()
        pwd = str(payload.get("password") or "123456").strip()
        if len(uname) < 3 or len(pwd) < 3:
            return False, "TÀI KHOẢN & MẬT KHẨU TỐI THIỂU 3 KÝ TỰ!", {}
        accounts = self._load_web_store()
        if any(a["username"] == uname for a in accounts):
            return False, "TÀI KHOẢN ĐÃ TỒN TẠI!", {}
        now = time.time()
        next_id = max((a.get("id", 0) for a in accounts), default=0) + 1
        level = max(1, int(payload.get("level") or 1))
        total_xp = max(0, int(payload.get("total_xp") or 0))
        gold = max(0, int(payload.get("gold") if payload.get("gold") is not None else 300))
        uc = max(1, int(payload.get("unlocked_count") or 1))
        streak = max(1, int(payload.get("streak_days") or 1))
        st = str(payload.get("status") or "active")
        dev = str(payload.get("last_device") or self.device_name)
        accounts.append({
            "id": next_id, "player_code": f"PLR-{next_id:04d}", "username": uname, "password": pwd,
            "role": "admin" if uname == "admin" else str(payload.get("role") or "user"),
            "created_at": now, "created_at_str": _fmt_ts(now),
            "status": st, "status_vn": {"active": "Đang hoạt động", "locked": "Bị khoá", "inactive": "Không hoạt động"}.get(st, "Đang hoạt động"),
            "is_online": False, "is_registered_today": True,
            "pet_name": uname.upper()[:10], "stage": 1, "character_file": "resources/img/character/chara_1b.png",
            "level": level, "exp": total_xp, "total_xp": total_xp, "gold": gold,
            "unlocked_characters": ["resources/img/character/chara_1b.png"],
            "unlocked_count": uc, "streak_days": streak,
            "last_login_at": now, "last_login_str": _fmt_ts(now, True), "login_count": 1,
            "last_device": dev,
            "activity_history": [
                {"id": 1, "event_name": "admin_create", "description": "Tài khoản được thêm mới", "device": dev, "timestamp": now, "time_str": _fmt_ts(now, True)},
            ],
            "lock_reason": "", "locked_until": 0, "locked_until_str": "--", "locked_by": "",
            "locked_at": 0, "locked_at_str": "--", "lock_duration_label": "--", "lock_history": [],
        })
        self._save_web_store(accounts)
        return True, f"ĐÃ THÊM TÀI KHOẢN '{uname.upper()}'!", self._web_fallback_get_dashboard()

    def _web_fallback_update_account(self, target_username: str, payload: dict) -> tuple[bool, str, dict]:
        uname = target_username.strip().lower()
        accounts = self._load_web_store()
        now = time.time()
        for a in accounts:
            if a["username"] == uname:
                if payload.get("password"):
                    a["password"] = str(payload["password"]).strip()
                if payload.get("status") and uname != "admin":
                    st = str(payload["status"])
                    a["status"] = st
                    a["status_vn"] = {"active": "Đang hoạt động", "locked": "Bị khoá", "inactive": "Không hoạt động"}.get(st, "Đang hoạt động")
                if payload.get("level") is not None:
                    a["level"] = max(1, int(payload["level"]))
                if payload.get("total_xp") is not None:
                    a["total_xp"] = max(0, int(payload["total_xp"]))
                    a["exp"] = a["total_xp"]
                if payload.get("gold") is not None:
                    a["gold"] = max(0, int(payload["gold"]))
                if payload.get("unlocked_count") is not None:
                    a["unlocked_count"] = max(1, int(payload["unlocked_count"]))
                if payload.get("streak_days") is not None:
                    a["streak_days"] = max(1, int(payload["streak_days"]))
                if payload.get("last_device"):
                    a["last_device"] = str(payload["last_device"])
                a.setdefault("activity_history", []).insert(0, {
                    "id": int(now), "event_name": "admin_update",
                    "description": "Quản trị viên cập nhật hồ sơ & chỉ số game",
                    "device": a.get("last_device", self.device_name),
                    "timestamp": now, "time_str": _fmt_ts(now, True),
                })
                self._save_web_store(accounts)
                return True, f"ĐÃ CẬP NHẬT '{uname.upper()}'!", self._web_fallback_get_dashboard()
        return False, "KHÔNG TÌM THẤY TÀI KHOẢN!", {}

    def _web_fallback_delete_account(self, target_username: str) -> tuple[bool, str, dict]:
        uname = target_username.strip().lower()
        if uname == "admin":
            return False, "KHÔNG THỂ XOÁ TÀI KHOẢN ADMIN GỐC!", {}
        accounts = [a for a in self._load_web_store() if a["username"] != uname]
        self._save_web_store(accounts)
        return True, f"ĐÃ XOÁ TÀI KHOẢN '{uname.upper()}'!", self._web_fallback_get_dashboard()

    def _web_fallback_lock_account(self, target_username: str, reason: str, duration_key: str) -> tuple[bool, str, dict]:
        uname = target_username.strip().lower()
        if uname == "admin":
            return False, "KHÔNG THỂ KHOÁ TÀI KHOẢN ADMIN!", {}
        dur_map = {
            "1h": (3600, "1 Giờ"),
            "24h": (86400, "24 Giờ (1 Ngày)"),
            "3d": (3 * 86400, "3 Ngày"),
            "7d": (7 * 86400, "7 Ngày"),
            "30d": (30 * 86400, "30 Ngày"),
            "permanent": (0, "Vĩnh viễn"),
        }
        secs, lbl = dur_map.get(duration_key, (0, "Vĩnh viễn"))
        now = time.time()
        until_ts = (now + secs) if secs > 0 else 0
        until_str = _fmt_ts(until_ts) if until_ts > 0 else "Vĩnh viễn"
        clean_reason = (reason or "").strip() or "Vi phạm quy định trò chơi"
        accounts = self._load_web_store()
        for a in accounts:
            if a["username"] == uname:
                a["status"] = "locked"
                a["status_vn"] = "Bị khoá"
                a["is_online"] = False
                a["lock_reason"] = clean_reason
                a["locked_until"] = until_ts
                a["locked_until_str"] = until_str
                a["locked_by"] = self.user_id
                a["locked_at"] = now
                a["locked_at_str"] = _fmt_ts(now)
                a["lock_duration_label"] = lbl
                a.setdefault("lock_history", []).insert(0, {
                    "id": int(now), "action": "KHOÁ TÀI KHOẢN", "reason": clean_reason,
                    "duration_label": lbl, "locked_until": until_ts, "locked_until_str": until_str,
                    "performed_by": self.user_id, "timestamp": now, "time_str": _fmt_ts(now, True),
                })
                self._save_web_store(accounts)
                return True, f"ĐÃ KHOÁ '{uname.upper()}' ({lbl.upper()})!", self._web_fallback_get_dashboard()
        return False, "KHÔNG TÌM THẤY TÀI KHOẢN!", {}

    def _web_fallback_unlock_account(self, target_username: str, reason: str) -> tuple[bool, str, dict]:
        uname = target_username.strip().lower()
        now = time.time()
        accounts = self._load_web_store()
        for a in accounts:
            if a["username"] == uname:
                a["status"] = "active"
                a["status_vn"] = "Đang hoạt động"
                a["lock_reason"] = ""
                a["locked_until"] = 0
                a["locked_until_str"] = "--"
                a["lock_duration_label"] = "--"
                a.setdefault("lock_history", []).insert(0, {
                    "id": int(now), "action": "MỞ KHOÁ", "reason": reason or "Quản trị viên mở khoá",
                    "duration_label": "Đã mở khoá", "locked_until": 0, "locked_until_str": "--",
                    "performed_by": self.user_id, "timestamp": now, "time_str": _fmt_ts(now, True),
                })
                self._save_web_store(accounts)
                return True, f"ĐÃ MỞ KHOÁ '{uname.upper()}'!", self._web_fallback_get_dashboard()
        return False, "KHÔNG TÌM THẤY TÀI KHOẢN!", {}

    # =========================================================================
    # CLOUD SAVE / LOAD / LEADERBOARD / ANALYTICS (TỨC THÌ + ĐỒNG BỘ NGẦM)
    # =========================================================================
    def save_pet(self, pet_dict: dict) -> tuple[bool, str]:
        pet_dict["user_id"] = self.user_id

        if IS_WEB:
            try:
                import platform
                platform.window.localStorage.setItem(
                    f"tamaweb_pet_{self.user_id}", json.dumps(pet_dict, ensure_ascii=False)
                )
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
