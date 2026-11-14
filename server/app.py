import os
import sys
from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
    list_users,
    save_pet_data,
    get_pet_data,
    get_top_leaderboard,
    log_analytics,
)

# Khởi tạo Database (PostgreSQL `tamaweb_db` + SQLite backup)
init_db()

app = FastAPI(title="4thmay - Nuôi thú cưng ảo API", version="2.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthRequest(BaseModel):
    username: str
    password: str


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


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "4thmay-tamaweb-api",
        "postgres_connected": is_using_postgres(),
    }


@app.post("/api/auth/register")
def api_register(req: AuthRequest):
    ok, msg, user = register_user(req.username, req.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "success", "message": msg, "user": user}


@app.post("/api/auth/login")
def api_login(req: AuthRequest):
    ok, msg, user = login_user(req.username, req.password)
    if not ok:
        raise HTTPException(status_code=401, detail=msg)
    return {"status": "success", "message": msg, "user": user}


@app.get("/api/users")
def api_list_users():
    return {
        "status": "success",
        "database": "PostgreSQL (tamaweb_db)" if is_using_postgres() else "SQLite",
        "users": list_users(),
    }


@app.post("/api/pet/save")
def api_save_pet(pet_data: PetSaveRequest):
    success = save_pet_data(pet_data.model_dump())
    if not success:
        raise HTTPException(status_code=500, detail="Lỗi khi lưu trạng thái thú cưng")
    return {"status": "success", "message": "Đã lưu thành công lên Cloud"}


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
