# Tamaweb Python: Pygame (2D) + Pygbag (WASM) + FastAPI + Database

Dự án chuyển đổi toàn diện game nuôi thú ảo **Tamaweb** sang nền tảng **Python thuần** kết hợp WebAssembly và Cloud Backend.

---

## 📁 Cấu trúc thư mục

```
tamaweb_python/
├── client/                     # Pygame Client (chạy cả Desktop và WebAssembly)
│   ├── main.py                 # Vòng lặp chính chuẩn asyncio (tương thích Pygbag)
│   ├── pet.py                  # Vòng đời, tiến hóa, trạng thái pet (Ăn, Ngủ, Tắm, Chơi)
│   ├── sprites.py              # Xử lý SpriteSheet, cắt frame 16x16, 24x24, 32x32
│   ├── audio.py                # Quản lý âm thanh hiệu ứng 8-bit retro
│   ├── api_client.py           # Kết nối FastAPI (Cloud Save, Leaderboard, Analytics)
│   ├── resources/              # Toàn bộ tài nguyên gốc (character, background, sounds...)
│   └── build/web/              # Gói WebAssembly đã build sẵn bởi Pygbag
│
├── server/                     # Backend FastAPI
│   ├── app.py                  # REST API endpoints (Cloud Save/Load, Leaderboard, Analytics)
│   ├── database.py             # SQLite nội bộ & chuẩn bị cho Supabase/PostgreSQL
│   └── tamaweb.db              # File database tự động tạo
│
├── run_desktop.command         # Click đúp để chơi ngay trên macOS (Pygame Desktop)
├── run_server.command          # Click đúp để bật FastAPI Backend (cổng 8000)
├── run_web.command             # Click đúp để chạy bản WebAssembly (cổng 8088)
└── build_wasm.sh               # Lệnh build lại WebAssembly bằng Pygbag
```

---

## 🎮 Cách chạy Game

### 1. Chơi trực tiếp trên Desktop (Pygame):
* **Cách nhanh:** Click đúp vào file `run_desktop.command`.
* **Bằng Terminal:**
  ```bash
  cd tamaweb_python
  python3 client/main.py
  ```

### 2. Chơi trên Trình duyệt Web (WebAssembly / Pygbag):
* **Cách nhanh:** Click đúp vào file `run_web.command` (sẽ mở `http://localhost:8088`).
* **Bằng Terminal:**
  ```bash
  cd tamaweb_python/client/build/web
  python3 -m http.server 8088
  ```

### 3. Bật FastAPI Backend (Leaderboard & Cloud Save):
* **Cách nhanh:** Click đúp vào file `run_server.command`.
* **API Docs (Swagger UI):** `http://localhost:8000/docs`

---

## 🕹️ Điều khiển trong Game

* **Phím số 1 / Click 'Cho ăn':** Cho thú cưng ăn bánh ngọt.
* **Phím số 2 / Click 'Đi ngủ':** Tắt đèn cho pet ngủ để hồi năng lượng.
* **Phím số 3 / Click 'Tắm rửa':** Dọn dẹp phân và tắm rửa sạch sẽ.
* **Phím số 4 / Click 'Chơi bóng':** Vui chơi tăng điểm kinh nghiệm (EXP).
* **Phím số 5 / Click 'Chữa bệnh':** Cho uống thuốc nếu pet bị ốm.
* **Phím S / Click 'Lưu Cloud':** Lưu tiến trình trực tiếp lên server FastAPI.
* **Phím L / Click 'Bảng XH':** Mở bảng xếp hạng thú cưng toàn cầu.
* **3 Nút tròn A - B - C:**
  * **A (Trái):** Di chuyển lựa chọn menu.
  * **B (Giữa):** Thực hiện hành động đã chọn.
  * **C (Phải):** Hủy hoặc chuyển tiếp.

---

## 🌐 Hướng dẫn Kết nối Supabase / PostgreSQL & Deploy

### 1. Kết nối Supabase / PostgreSQL:
Trong file `server/database.py`, bạn có thể đổi chuỗi kết nối từ SQLite sang PostgreSQL/Supabase:
```python
# Cài đặt: pip install psycopg2-binary
import psycopg2

DATABASE_URL = "postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres"
# Thay connect bằng psycopg2.connect(DATABASE_URL)
```

### 2. Deploy WebAssembly lên Web (Firebase Hosting / Vercel):
Thư mục `client/build/web` chứa toàn bộ static files (`index.html`, `client.apk`, `client.tar.gz`).
Bạn chỉ cần upload thư mục này lên **Firebase Hosting**, **Vercel** hoặc **GitHub Pages**.

### 3. Deploy Backend FastAPI lên Cloud (Render / Railway):
* Thư mục `server/` có thể deploy trực tiếp lên **Render** hoặc **Railway** với start command:
  ```bash
  uvicorn app:app --host 0.0.0.0 --port 8000
  ```
