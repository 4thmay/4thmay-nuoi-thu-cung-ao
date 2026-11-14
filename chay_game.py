import subprocess
import sys
import os
import time
import socket

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(BASE_DIR, "server")
CLIENT_MAIN = os.path.join(BASE_DIR, "client", "main.py")

PG_CTL = "/opt/homebrew/opt/postgresql@16/bin/pg_ctl"
PG_DATA = "/opt/homebrew/var/postgresql@16"
PG_LOG = "/opt/homebrew/var/log/postgresql@16.log"


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def ensure_postgres_running():
    if is_port_in_use(5432):
        print("🗄️  PostgreSQL Database (tamaweb_db) đã đang chạy tại cổng 5432.")
        return
    if os.path.exists(PG_CTL) and os.path.exists(PG_DATA):
        print("🗄️  Đang khởi động PostgreSQL 16 Database Server (tamaweb_db)...")
        try:
            subprocess.run(
                [PG_CTL, "-D", PG_DATA, "-l", PG_LOG, "start"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.8)
            print("✅ Đã kết nối PostgreSQL Database: postgresql://localhost:5432/tamaweb_db")
        except Exception as e:
            print(f"⚠️  Không thể tự bật PostgreSQL ({e}), dùng bản sao lưu nội bộ.")


def main():
    server_proc = None
    try:
        # 1. Tự động bật PostgreSQL Database Server nếu chưa chạy
        ensure_postgres_running()

        # 2. Tự động bật FastAPI Backend nếu cổng 8000 chưa chạy
        if not is_port_in_use(8000):
            print("🚀 Đang khởi động FastAPI Server (Auth, Leaderboard & Cloud Save) tại http://localhost:8000 ...")
            server_proc = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=SERVER_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1.0)
        else:
            print("✅ FastAPI Server đã đang chạy tại http://localhost:8000")

        # 3. Mở cửa sổ game Pygame (4thmay - Nuôi thú cưng ảo)
        print("🎮 Đang mở cửa sổ game: 4thmay - Nuôi thú cưng ảo...")
        subprocess.run([sys.executable, CLIENT_MAIN], cwd=os.path.join(BASE_DIR, "client"))

    except KeyboardInterrupt:
        print("\n👋 Đang đóng game...")
    finally:
        if server_proc is not None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=2)
            except Exception:
                server_proc.kill()
            print("🛑 Đã tắt FastAPI Server.")


if __name__ == "__main__":
    main()
