import os
import sys
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
import uvicorn

_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from database import (
    init_db,
    is_using_postgres,
    register_user,
    login_user,
    logout_user,
    list_users,
    save_pet_data,
    save_pet_data_checked,
    get_pet_data,
    get_top_leaderboard,
    log_analytics,
    get_admin_dashboard_data,
    admin_create_account,
    admin_update_account,
    admin_delete_account,
    lock_user_account,
    unlock_user_account,
)

# Khởi tạo Database (PostgreSQL `tamaweb_db` + SQLite backup)
init_db()

app = FastAPI(title="4thmay - Nuôi thú cưng ảo API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path in ("/", "/index.html") or path.endswith((".apk", ".tar.gz", ".js", ".json")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


class AuthRequest(BaseModel):
    username: str
    password: str
    device: str = "Web Browser (Tamaweb WASM)"


class LogoutRequest(BaseModel):
    username: str


class PetSaveRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_id: str = "guest_1"
    pet_name: str = "Tama"
    stage: int = 1
    character_file: str = "resources/img/character/chara_1b.png"
    level: int = 1
    exp: int = 0
    hunger: float = 100.0
    energy: float = 100.0
    hygiene: float = 100.0
    happiness: float = 100.0
    age_seconds: int = 0


class AnalyticsEventRequest(BaseModel):
    user_id: str = "guest_1"
    event_name: str
    payload: Dict[str, Any] = {}


class AdminAccountCreateRequest(BaseModel):
    admin_user: str = "admin"
    username: str
    password: str = "123456"
    role: str = "user"
    status: str = "active"
    level: int = 1
    total_xp: int = 0
    gold: int = 300
    unlocked_count: int = 1
    streak_days: int = 1
    last_device: str = "Web Browser (Tamaweb WASM)"


class AdminAccountUpdateRequest(BaseModel):
    admin_user: str = "admin"
    target_username: str
    password: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    level: Optional[int] = None
    total_xp: Optional[int] = None
    gold: Optional[int] = None
    unlocked_count: Optional[int] = None
    streak_days: Optional[int] = None
    login_count: Optional[int] = None
    last_device: Optional[str] = None
    is_online: Optional[int] = None


class AdminAccountDeleteRequest(BaseModel):
    admin_user: str = "admin"
    target_username: str


class AdminLockRequest(BaseModel):
    admin_user: str = "admin"
    target_username: str
    reason: str = "Vi phạm quy định trò chơi"
    duration_key: str = "24h"


class AdminUnlockRequest(BaseModel):
    admin_user: str = "admin"
    target_username: str
    reason: str = "Quản trị viên mở khoá tài khoản"


def _require_admin(admin_user: str):
    if (admin_user or "").strip().lower() != "admin":
        raise HTTPException(status_code=403, detail="CHỈ QUẢN TRỊ VIÊN (ADMIN) MỚI CÓ QUYỀN TRUY CẬP!")


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "4thmay-tamaweb-api",
        "postgres_connected": is_using_postgres(),
    }


@app.post("/api/auth/register")
def api_register(req: AuthRequest):
    ok, msg, user = register_user(req.username, req.password, req.device)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg, "user": user}


@app.post("/api/auth/login")
def api_login(req: AuthRequest):
    ok, msg, user = login_user(req.username, req.password, req.device)
    if not ok:
        raise HTTPException(status_code=401, detail=msg)
    uname = req.username.strip().lower()
    pet_data = get_pet_data(uname)
    resp: Dict[str, Any] = {"status": "success", "message": msg, "user": user, "pet_data": pet_data}
    if uname == "admin" or (user and user.get("role") == "admin"):
        resp["dashboard"] = get_admin_dashboard_data()
    return resp


@app.post("/api/auth/logout")
def api_logout(req: LogoutRequest):
    logout_user(req.username)
    return {"status": "success", "message": "ĐÃ ĐĂNG XUẤT!"}


@app.get("/api/users")
def api_list_users():
    return {
        "status": "success",
        "database": "PostgreSQL (tamaweb_db)" if is_using_postgres() else "SQLite",
        "users": list_users(),
    }


# =============================================================================
# CÁC API QUẢN TRỊ TÀI KHOẢN (CHỈ ADMIN MỚI CÓ QUYỀN TRUY CẬP)
# =============================================================================

@app.get("/api/admin/dashboard")
def api_admin_dashboard(
    admin_user: str = Query("admin"),
    x_admin_user: Optional[str] = Header(None),
):
    caller = x_admin_user or admin_user
    _require_admin(caller)
    return get_admin_dashboard_data()


@app.post("/api/admin/accounts/create")
def api_admin_create_account(req: AdminAccountCreateRequest):
    _require_admin(req.admin_user)
    ok, msg, data = admin_create_account(req.model_dump(), performed_by=req.admin_user)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg, "account": data, "dashboard": get_admin_dashboard_data()}


@app.post("/api/admin/accounts/update")
def api_admin_update_account(req: AdminAccountUpdateRequest):
    _require_admin(req.admin_user)
    ok, msg = admin_update_account(req.target_username, req.model_dump(exclude_none=True), performed_by=req.admin_user)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg, "dashboard": get_admin_dashboard_data()}


@app.post("/api/admin/accounts/delete")
def api_admin_delete_account(req: AdminAccountDeleteRequest):
    _require_admin(req.admin_user)
    ok, msg = admin_delete_account(req.target_username, performed_by=req.admin_user)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg, "dashboard": get_admin_dashboard_data()}


@app.post("/api/admin/accounts/lock")
def api_admin_lock_account(req: AdminLockRequest):
    _require_admin(req.admin_user)
    ok, msg = lock_user_account(
        req.target_username,
        reason=req.reason,
        duration_key=req.duration_key,
        performed_by=req.admin_user,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg, "dashboard": get_admin_dashboard_data()}


@app.post("/api/admin/accounts/unlock")
def api_admin_unlock_account(req: AdminUnlockRequest):
    _require_admin(req.admin_user)
    ok, msg = unlock_user_account(
        req.target_username,
        performed_by=req.admin_user,
        reason=req.reason,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg, "dashboard": get_admin_dashboard_data()}


@app.post("/api/pet/save")
def api_save_pet(pet_data: PetSaveRequest):
    success, msg, flagged = save_pet_data_checked(pet_data.model_dump())
    if flagged:
        raise HTTPException(status_code=403, detail=msg)
    if not success:
        raise HTTPException(status_code=500, detail="Lỗi khi lưu trạng thái thú cưng")
    return {"status": "success", "message": msg}


@app.get("/api/pet/load/{user_id}")
def api_load_pet(user_id: str):
    data = get_pet_data(user_id)
    if not data:
        return {"status": "not_found", "data": None}
    return {"status": "success", "data": data}


@app.get("/api/leaderboard")
def api_leaderboard(limit: int = 10):
    rankings = get_top_leaderboard(limit)
    return {"status": "success", "leaderboard": rankings}


@app.post("/api/analytics/event")
def api_log_event(req: AnalyticsEventRequest):
    log_analytics(req.user_id, req.event_name, req.payload)
    return {"status": "logged"}


_WASM_DIR = os.path.join(os.path.dirname(_SERVER_DIR), "client", "build", "web")
if os.path.isdir(_WASM_DIR):
    app.mount("/", StaticFiles(directory=_WASM_DIR, html=True), name="wasm_web")
else:
    @app.get("/")
    def read_root():
        return {
            "message": "4thmay - Nuôi thú cưng ảo Backend API đang hoạt động!",
            "database": "PostgreSQL (tamaweb_db)" if is_using_postgres() else "SQLite (tamaweb.db)",
        }


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
