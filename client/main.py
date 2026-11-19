import asyncio
import datetime
import math
import random
import pygame

from api_client import IS_WEB, APIClient
from audio import SoundManager
from definitions import (
    ACCESSORIES,
    BACKGROUND_PATTERNS,
    FOODS,
    FURNITURES,
    ITEMS,
    NPC_CHARACTERS,
    OUTSIDE_ACTIVITIES,
    PLANTS,
    ROOM_BACKGROUNDS,
    SHELL_BACKGROUNDS,
    STAGE_CHARACTERS,
)
from pet import GARDEN_PATCH_POSITIONS, STAGE_INFO, Pet
from sprites import SpriteSheet, get_pixel_font, load_image

# Kích thước cửa sổ chuẩn Tamaweb Widescreen (1280x720)
WIN_W, WIN_H = 1280, 720

# Kích thước màn hình LCD gốc của Tamaweb là 96x96, hiển thị phóng đại 2x (192x192) trong vỏ máy
LCD_NATIVE = 96
LCD_SCALE = 2
LCD_DISPLAY = LCD_NATIVE * LCD_SCALE  # 192x192

# Bảng màu chuẩn từ styles.css (.theme-default) của Tamaweb
COLOR_BG_NAVAJO = (255, 222, 173)       # #FFDEAD
COLOR_STRIPE_A1 = (255, 221, 184)       # #ffddb8
COLOR_STRIPE_A2 = (255, 229, 202)       # #ffe5ca
COLOR_STRIPE_B1 = (255, 202, 244)       # #ffcaf4
COLOR_STRIPE_B2 = (255, 229, 202)       # #ffe5ca
COLOR_SURFACE = (255, 244, 232)         # #fff4e8
COLOR_SURFACE_SHADOW = (245, 222, 179)  # #f5deb3
COLOR_SURFACE_ACTIVE = (255, 198, 138)  # #ffc68a
COLOR_BORDER = (255, 179, 98)           # #ffb362
COLOR_TEXT_ORANGE = (255, 128, 0)       # #ff8000
COLOR_TEXT_SHADOW = (255, 207, 157)     # #ffcf9d
COLOR_GREEN = (98, 219, 68)             # #62db44
COLOR_RED = (237, 37, 78)               # #ED254E
COLOR_PURPLE_BACK = (61, 0, 255)        # #3d00ff

# 9 ô Menu chính (3x3 Grid) chuẩn Definitions.js (main_menu) & styles.css (--mm-clr-1..8)
MAIN_GRID_ITEMS = [
    {"id": "stats",    "color": (250, 145, 137), "icon": "dashboard"},  # #fa9189
    {"id": "feeding",  "color": (252, 174, 124), "icon": "cutlery"},    # #fcae7c
    {"id": "bath",     "color": (153, 204, 255), "icon": "bath"},       # #99ccff
    {"id": "care",     "color": (255, 204, 153), "icon": "care_home"},  # #ffcc99
    {"id": "activity", "color": (164, 228, 169), "icon": "door"},       # #a4e4a9
    {"id": "stuff",    "color": (251, 136, 255), "icon": "box"},        # #fb88ff
    {"id": "phone",    "color": (255, 153, 204), "icon": "phone"},      # #ff99cc
    {"id": "settings", "color": (209, 189, 255), "icon": "gear"},       # #d1bdff
    {"id": "back",     "color": (61, 0, 255),    "icon": "back"},       # #3d00ff
]

SOCIAL_POSTS = [
    {"author": "MAMETCHI", "sprite": "resources/img/character/chara_133b.png", "bg": "resources/img/outside/park_02.png", "text": "HÔM NAY TRỜI ĐẸP QUÁ! ĐI DẠO CÔNG VIÊN #VUI", "likes": 42, "liked": False},
    {"author": "KUCHIPATCHI", "sprite": "resources/img/character/chara_136b.png", "bg": "resources/img/background/house/kitchen_03.png", "text": "VỪA NẤU MÓN LẨU RỒNG CAY SIÊU NGON LUÔN!", "likes": 89, "liked": False},
    {"author": "LOVELITCHI", "sprite": "resources/img/character/chara_150b.png", "bg": "resources/img/background/house/mall_interior_01.png", "text": "MỚI SẮM VƯƠNG MIỆN XINH XẮN Ở TRUNG TÂM!", "likes": 124, "liked": False},
    {"author": "MEMETCHI", "sprite": "resources/img/character/chara_140b.png", "bg": "resources/img/background/house/beach_01.png", "text": "KỲ NGHỈ BIỂN TUYỆT VỜI QUÁ MỌI NGƯỜI ƠI!", "likes": 67, "liked": False},
]


def create_egg_mask(w: int, h: int) -> pygame.Surface:
    """Mặt nạ hình quả trứng chuẩn CSS .dom-shell.shell-shape-6: border-radius: 50% / 60% 60% 40% 40%"""
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w / 2.0
    split_y = h * 0.58
    rx = w / 2.0 - 2.0
    ry_top = split_y - 2.0
    ry_bot = (h - split_y) - 2.0

    for y in range(h):
        dy = (y - split_y) / (ry_top if y < split_y else ry_bot)
        if abs(dy) <= 1.0:
            half_span = rx * math.sqrt(max(0.0, 1.0 - dy * dy))
            x1 = int(max(0, cx - half_span))
            x2 = int(min(w - 1, cx + half_span))
            pygame.draw.line(mask, (255, 255, 255, 255), (x1, y), (x2, y))
    return mask


def build_dom_shell_surface(pattern_path: str, w: int = 320, h: int = 400) -> tuple[pygame.Surface, list[pygame.Surface]]:
    """
    Tạo bề mặt vỏ trứng Tamagotchi (.dom-shell 320x400) phủ họa tiết shell_background_XX.png
    theo chuẩn CSS `background: 50% 50% / cover` + đổ bóng inset 3D + 3 nút tròn 32px.
    """
    pattern = load_image(pattern_path)
    cover_size = max(w, h)
    scaled_pat = pygame.transform.smoothscale(pattern, (cover_size, cover_size))
    tiled = pygame.Surface((w, h), pygame.SRCALPHA)
    tiled.blit(scaled_pat, ((w - cover_size) // 2, (h - cover_size) // 2))

    mask = create_egg_mask(w, h)
    shell = pygame.Surface((w, h), pygame.SRCALPHA)
    shell.blit(tiled, (0, 0))
    shell.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    # Viền nổi khối 3D quanh vỏ trứng
    cx = w / 2.0
    split_y = h * 0.58
    rx = w / 2.0 - 2.0
    ry_top = split_y - 2.0
    ry_bot = (h - split_y) - 2.0

    pts = []
    for deg in range(0, 360, 2):
        rad = math.radians(deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        ry = ry_top if sin_a < 0 else ry_bot
        pts.append((int(cx + rx * cos_a), int(split_y + ry * sin_a)))

    pygame.draw.polygon(shell, (210, 190, 170, 95), pts, 8)
    pygame.draw.polygon(shell, (175, 155, 135, 85), pts, 3)

    # 3 nút bấm tròn 32x32 màu kem ấm áp chuẩn .dom-shell .shell-btn trong Tamaweb
    buttons = []
    btn_size = 36
    for _ in range(3):
        btn_surf = pygame.Surface((btn_size, btn_size), pygame.SRCALPHA)
        pygame.draw.circle(btn_surf, (170, 142, 112, 135), (btn_size // 2, btn_size // 2 + 2), 15)
        pygame.draw.circle(btn_surf, (238, 214, 184, 255), (btn_size // 2, btn_size // 2), 14)
        pygame.draw.circle(btn_surf, (250, 234, 212, 255), (btn_size // 2 - 2, btn_size // 2 - 2), 10)
        pygame.draw.circle(btn_surf, (198, 172, 142, 200), (btn_size // 2, btn_size // 2), 14, 1)
        buttons.append(btn_surf)

    return shell, buttons


def draw_grid_icon(surf: pygame.Surface, icon_name: str, cx: int, cy: int):
    """Vẽ đúng bộ 9 icon của Tamaweb Main Menu (fa-dashboard, fa-cutlery, fa-bath, fa-house-chimney-user, fa-door-open, fa-box-open, fa-mobile-alt, fa-gear, fa-arrow-left)"""
    white = (255, 255, 255)
    shadow = (100, 50, 20, 90)
    for ox, oy, col in [(0, 2, shadow), (0, 0, white)]:
        x, y = cx + ox, cy + oy
        if icon_name == "dashboard":
            # Đồng hồ đo (fa-dashboard / gauge)
            pygame.draw.circle(surf, col, (x, y + 2), 11, 3)
            pygame.draw.rect(surf, col, (x - 8, y + 7, 16, 3))
            pygame.draw.line(surf, col, (x, y + 2), (x + 5, y - 4), 3)
            pygame.draw.circle(surf, col, (x, y + 2), 3)
        elif icon_name == "cutlery":
            # Dao & Nĩa (fa-cutlery)
            pygame.draw.rect(surf, col, (x - 7, y - 10, 2, 8))
            pygame.draw.rect(surf, col, (x - 4, y - 10, 2, 8))
            pygame.draw.rect(surf, col, (x - 1, y - 10, 2, 8))
            pygame.draw.rect(surf, col, (x - 7, y - 2, 8, 3))
            pygame.draw.rect(surf, col, (x - 4, y + 1, 3, 10))
            pygame.draw.rect(surf, col, (x + 4, y - 10, 4, 12), border_radius=2)
            pygame.draw.rect(surf, col, (x + 5, y + 2, 3, 9))
        elif icon_name == "bath":
            # Bồn tắm (fa-bath)
            pygame.draw.rect(surf, col, (x - 11, y - 1, 22, 9), border_radius=4)
            pygame.draw.rect(surf, col, (x - 12, y - 3, 24, 3), border_radius=1)
            pygame.draw.circle(surf, col, (x - 5, y - 7), 2)
            pygame.draw.circle(surf, col, (x + 1, y - 8), 3)
            pygame.draw.circle(surf, col, (x + 6, y - 6), 2)
            pygame.draw.rect(surf, col, (x - 8, y + 8, 3, 3))
            pygame.draw.rect(surf, col, (x + 5, y + 8, 3, 3))
        elif icon_name == "care_home":
            # Ngôi nhà chăm sóc (fa-house-chimney-user)
            pygame.draw.polygon(surf, col, [(x, y - 11), (x - 12, y - 1), (x + 12, y - 1)])
            pygame.draw.rect(surf, col, (x - 9, y - 1, 18, 12), border_radius=2)
            heart_col = (255, 195, 145) if col == white else col
            pygame.draw.circle(surf, heart_col, (x, y + 3), 3)
            pygame.draw.rect(surf, heart_col, (x - 4, y + 7, 8, 3), border_radius=1)
        elif icon_name == "door":
            # Cánh cửa mở đi chơi (fa-door-open)
            pygame.draw.rect(surf, col, (x - 8, y - 10, 16, 20), 3, border_radius=2)
            pygame.draw.rect(surf, col, (x - 5, y - 8, 9, 16))
            dot_col = (164, 228, 169) if col == white else col
            pygame.draw.circle(surf, dot_col, (x + 2, y), 2)
        elif icon_name == "box":
            # Hộp đồ mở (fa-box-open)
            pygame.draw.rect(surf, col, (x - 10, y - 3, 20, 13), border_radius=2)
            pygame.draw.polygon(surf, col, [(x - 10, y - 3), (x - 14, y - 8), (x - 2, y - 8), (x, y - 3)])
            pygame.draw.polygon(surf, col, [(x + 10, y - 3), (x + 14, y - 8), (x + 2, y - 8), (x, y - 3)])
            rib_col = (240, 120, 245) if col == white else col
            pygame.draw.rect(surf, rib_col, (x - 2, y - 3, 4, 13))
        elif icon_name == "phone":
            # Điện thoại di động (fa-mobile-alt)
            pygame.draw.rect(surf, col, (x - 7, y - 11, 14, 22), border_radius=3)
            scr_col = (255, 153, 204) if col == white else col
            pygame.draw.rect(surf, scr_col, (x - 5, y - 8, 10, 14))
            pygame.draw.circle(surf, scr_col, (x, y + 8), 2)
        elif icon_name == "gear":
            # Bánh răng cài đặt (fa-gear)
            pygame.draw.circle(surf, col, (x, y), 8, 4)
            for deg in range(0, 360, 45):
                rad = math.radians(deg)
                gx = int(x + math.cos(rad) * 9)
                gy = int(y + math.sin(rad) * 9)
                pygame.draw.circle(surf, col, (gx, gy), 3)
            pygame.draw.circle(surf, (209, 189, 255) if col == white else col, (x, y), 3)
        elif icon_name == "back":
            # Mũi tên quay lại (fa-arrow-left)
            pygame.draw.polygon(surf, col, [(x - 9, y), (x - 1, y - 7), (x - 1, y + 7)])
            pygame.draw.rect(surf, col, (x - 1, y - 3, 10, 6), border_radius=1)


class TamawebApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("4thmay - Nuôi thú cưng ảo")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()

        self.lcd_native = pygame.Surface((LCD_NATIVE, LCD_NATIVE), pygame.SRCALPHA)
        self.lcd_display = pygame.Surface((LCD_DISPLAY, LCD_DISPLAY), pygame.SRCALPHA)

        self.sound = SoundManager()
        self.backend = APIClient("http://127.0.0.1:8000")
        self.pet = Pet(self.sound)

        # Tự động nạp save gần nhất nếu có (trên desktop)
        if not IS_WEB:
            saved_data = self.backend.load_pet()
            if saved_data:
                self.pet.load_from_dict(saved_data)

        # Font chữ PixelColeco chuẩn từ Tamaweb
        self.font_xs = get_pixel_font(10)
        self.font_sm = get_pixel_font(12)
        self.font_md = get_pixel_font(14)
        self.font_lg = get_pixel_font(18)

        # Con trỏ bàn tay pixel (pointer_right.png) chuẩn styles.css dòng 595
        self.pointer_img = pygame.transform.scale(
            load_image("resources/img/ui/pointer_right.png"), (22, 18)
        )
        self.tap_hand_img = pygame.transform.scale(
            load_image("resources/img/ui/tap_01.png"), (28, 28)
        )

        # Họa tiết nền cuộn chéo & Lá cây trang trí viền
        self.pattern_idx = 0
        self.bg_pattern = load_image(BACKGROUND_PATTERNS[0][1])
        self.bg_scroll_x = 0.0
        self.bg_scroll_y = 0.0

        self.logo_img = load_image("resources/img/ui/logo_trans_01.png")
        self.logo_scaled = pygame.transform.smoothscale(self.logo_img, (150, 62))
        self.classic_front_img = load_image("resources/img/ui/Front.png")
        self.classic_front_scaled = pygame.transform.scale(
            self.classic_front_img,
            (self.classic_front_img.get_width() * 3, self.classic_front_img.get_height() * 3),
        )

        self.leaves = self._build_border_foliage()

        # Bầu trời theo giờ thực
        self.sky_images = {
            "morning": load_image("resources/img/background/sky/morning.png"),
            "afternoon": load_image("resources/img/background/sky/afternoon.png"),
            "evening": load_image("resources/img/background/sky/evening.png"),
            "night": load_image("resources/img/background/sky/night.png"),
        }

        # Cảnh nền trong game
        self.scene_bgs = {
            "park": load_image("resources/img/background/outside/park_02.png", season="spring"),
            "arcade": load_image("resources/img/background/house/arcade_01.png"),
            "clinic": load_image("resources/img/background/house/clinic_01.png"),
            "restaurant": load_image("resources/img/background/house/restaurant_01.png"),
            "mall": load_image("resources/img/background/house/mall_interior_01.png"),
            "market": load_image("resources/img/background/outside/market_01.png", season="spring"),
            "school": load_image("resources/img/background/house/classroom_01.png"),
            "fortune": load_image("resources/img/background/house/fortune_teller_01.png"),
            "work": load_image("resources/img/background/house/office_01.png"),
            "underworld": load_image("resources/img/background/house/devil_town_01.png"),
            "post_office": load_image("resources/img/background/house/post_office_01.png"),
            "getaways": load_image("resources/img/background/house/beach_01.png"),
            "backyard": load_image("resources/img/background/outside/garden_01.png", season="spring"),
            "garden": load_image("resources/img/background/outside/garden_inner_01.png", season="spring"),
            "parents": load_image("resources/img/background/house/parents_house_01.png"),
            "wedding": load_image("resources/img/background/house/wedding_01.png"),
            "online_hub": load_image("resources/img/background/house/online_hub_01.png"),
            "activities_base": load_image("resources/img/background/outside/activities_base_01.png", season="spring"),
        }

        # Vỏ trứng mặc định chuẩn Tamaweb (shell_background_13.png, 320x400)
        self.shell_idx = 0
        self.shell_w, self.shell_h = 320, 400
        self.shell_x = (WIN_W - self.shell_w) // 2
        self.shell_y = (WIN_H - self.shell_h) // 2
        self._rebuild_shell()

        # Màn hình LCD 192x192 chính giữa vỏ trứng
        self.lcd_rect = pygame.Rect(
            self.shell_x + (self.shell_w - LCD_DISPLAY) // 2,
            self.shell_y + 104,
            LCD_DISPLAY,
            LCD_DISPLAY,
        )

        # 3 nút bấm vật lý trên vỏ trứng (.dom-shell .shell-btn: left, main, right)
        self.shell_btn_rects = [
            pygame.Rect(self.shell_x + 78, self.shell_y + 316, 36, 36),
            pygame.Rect(self.shell_x + 142, self.shell_y + 332, 36, 36),
            pygame.Rect(self.shell_x + 206, self.shell_y + 316, 36, 36),
        ]
        self.pressed_shell_btn = -1
        self.pressed_timer = 0.0

        # Bề mặt sọc chéo chuẩn .generic-grid-container & .generic-list-container
        self.striped_bg_a = self._create_striped_surface(LCD_DISPLAY, LCD_DISPLAY, COLOR_STRIPE_A1, COLOR_STRIPE_A2)
        self.striped_bg_b = self._create_striped_surface(LCD_DISPLAY, LCD_DISPLAY, COLOR_STRIPE_B1, COLOR_STRIPE_B2)

        # Trạng thái điều hướng UI bên trong màn hình LCD
        self.menu_state = None
        self.menu_stack = []
        self.cursor_idx = 0
        self.slider_idx = 0
        self.activity_idx = 0
        self.cook_sel = []
        self.post_idx = 0
        self.leaderboard_rows = []
        self.clickable_lcd_areas = []

        # Trạng thái Minigame (1: Falling Coins, 2: Guess Number, 3: School Card Match)
        self.mg_type = "falling"
        self.mg_basket_x = 40.0
        self.mg_score = 0
        self.mg_timer = 15.0
        self.mg_coins = []
        self.mg_spawn_tick = 0.0
        self.mg_secret_num = 5
        self.mg_guess_msg = "GUESS 1-9!"

        self.toast_text = ""
        self.toast_timer = 0.0
        self.auto_save_timer = 0.0

        # =====================================================================
        # TRẠNG THÁI MÀN HÌNH ĐĂNG NHẬP & ĐĂNG KÝ (BẮT BUỘC TRƯỚC KHI VÀO GAME)
        # =====================================================================
        self.is_authenticated = False
        self.auth_mode = "login"       # "login" hoặc "register"
        self.auth_username = ""
        self.auth_password = ""
        self.auth_confirm = ""
        self.auth_focus = 0            # 0: Tài khoản, 1: Mật khẩu, 2: Nhập lại MK (khi đăng ký)
        self.auth_show_pw = False
        self.auth_msg = ""
        self.auth_msg_color = COLOR_RED
        self.auth_click_areas = []
        self.window_click_areas = []
        self.auth_anim_tick = 0.0

        # Trạng thái xác thực bất đồng bộ (tránh tuyệt đối đơ/đứng trang)
        self.auth_in_progress = False
        self.auth_in_progress_time = 0.0
        self.auth_pending_mode = "login"
        self.auth_pending_user = ""
        self.auth_pending_pwd = ""

        # Các nhân vật Mascot Tamaweb trang trí trên màn hình Đăng nhập / Đăng ký
        self.auth_mascots = [
            SpriteSheet("resources/img/character/chara_133b.png", 32, 4, 4),  # Mametchi
            SpriteSheet("resources/img/character/chara_150b.png", 32, 4, 4),  # Lovelitchi
            SpriteSheet("resources/img/character/chara_152b.png", 32, 4, 4),  # Mimitchi
            SpriteSheet("resources/img/character/chara_136b.png", 32, 4, 4),  # Kuchipatchi
        ]
        self.striped_card_hdr = self._create_striped_surface(348, 36, COLOR_STRIPE_A1, COLOR_STRIPE_A2)

        # =====================================================================
        # TRẠNG THÁI TRANG QUẢN TRỊ VIÊN - QUẢN LÝ TÀI KHOẢN (CHỈ ADMIN)
        # =====================================================================
        self.is_admin_mode = False
        self.admin_dashboard = {}
        self.admin_stats = {
            "total_accounts": 0,
            "active_accounts": 0,
            "new_today_accounts": 0,
            "locked_accounts": 0,
            "online_players": 0,
            "inactive_accounts": 0,
        }
        self.admin_accounts = []
        self.admin_filter = "all"          # "all", "active", "today", "locked", "online", "inactive"
        self.admin_search_query = ""
        self.admin_search_focused = False
        self.admin_selected_username = ""
        self.admin_page = 0
        self.admin_detail_tab = "all_4"    # "all_4", "part1", "part2", "part3", "part4", "locked_list"
        self.admin_show_user_pw = False
        self.admin_modal = None            # None, "add", "edit", "lock", "delete"
        self.admin_modal_focus = 0
        self.admin_form = {
            "username": "",
            "password": "",
            "status": "active",
            "level": "1",
            "total_xp": "0",
            "gold": "300",
            "unlocked_count": "1",
            "streak_days": "1",
            "last_device": "Web Browser (Tamaweb WASM)",
            "lock_reason": "Gian lận Coin & XP (Cheat/Hack)",
            "lock_duration_key": "24h",
        }
        self.admin_notice_msg = ""
        self.admin_notice_color = COLOR_GREEN
        self.admin_notice_timer = 0.0
        self.admin_click_areas = []
        self.admin_modal_click_areas = []
        self.admin_sprite_cache = {}
        self.striped_admin_hdr = self._create_striped_surface(1180, 52, COLOR_STRIPE_A1, COLOR_STRIPE_A2)
        self.striped_admin_sec = self._create_striped_surface(694, 28, COLOR_STRIPE_B1, COLOR_STRIPE_B2)

        self.backend.send_analytics("game_start", {"ui": "full_tamaweb_1_to_1"})

    def _build_border_foliage(self) -> list[tuple[pygame.Surface, int, int]]:
        """Tạo viền lá cây bao quanh 4 cạnh màn hình 1280x720 chuẩn giao diện Tamaweb (.foliage-container)"""
        l_orange = load_image("resources/img/ui/decoration/leaf_02.png")
        l_ivy = load_image("resources/img/ui/decoration/leaf_04.png")
        l_green = load_image("resources/img/ui/decoration/leaf_05.png")

        def make_leaf(src: pygame.Surface, sz: int, angle: float, flip_x: bool = False) -> pygame.Surface:
            base = pygame.transform.smoothscale(src, (sz, sz))
            if flip_x:
                base = pygame.transform.flip(base, True, False)
            rot = pygame.transform.rotate(base, angle)
            rw, rh = rot.get_size()
            out = pygame.Surface((rw + 8, rh + 8), pygame.SRCALPHA)
            try:
                msk = pygame.mask.from_surface(rot)
                shd = msk.to_surface(setcolor=(50, 32, 12, 70), unsetcolor=(0, 0, 0, 0))
                out.blit(shd, (4, 6))
            except Exception:
                pass
            out.blit(rot, (0, 0))
            return out

        specs = [
            # Cạnh trên (nghiêng mềm dọc viền trên giống hệt ảnh mẫu Tamaweb)
            (l_orange, 145, 140, False, -38, -56),
            (l_green,  150, 215, False, 52,  -62),
            (l_green,  140, 148, True,  140, -58),
            (l_green,  135, 210, False, 225, -62),
            (l_orange, 130, 145, False, 315, -58),
            (l_ivy,    155, 180, False, 415, -62),
            (l_green,  140, 215, False, 510, -64),
            (l_green,  145, 150, True,  615, -64),
            (l_green,  145, 210, False, 765, -60),
            (l_green,  155, 148, True,  845, -56),
            (l_green,  140, 205, False, 965, -58),
            (l_orange, 135, 218, True,  1048, -60),
            (l_green,  150, 155, False, 1135, -58),
            (l_orange, 145, 215, True,  1202, -52),

            # Cạnh dưới (nghiêng mềm dọc viền dưới)
            (l_green,  145, -32, False, -32, WIN_H - 96),
            (l_ivy,    155, 18,  False, 55,  WIN_H - 96),
            (l_green,  135, -28, True,  152, WIN_H - 88),
            (l_orange, 135, 28,  False, 248, WIN_H - 90),
            (l_green,  155, -24, False, 345, WIN_H - 98),
            (l_green,  150, 26,  True,  435, WIN_H - 96),
            (l_green,  135, -22, False, 530, WIN_H - 88),
            (l_orange, 130, 25,  True,  645, WIN_H - 86),
            (l_orange, 138, -28, False, 755, WIN_H - 90),
            (l_ivy,    155, 14,  True,  835, WIN_H - 96),
            (l_green,  150, -25, False, 938, WIN_H - 98),
            (l_green,  145, 28,  True,  1045, WIN_H - 94),
            (l_ivy,    155, -15, False, 1140, WIN_H - 98),
            (l_green,  145, 32,  True,  1195, WIN_H - 96),

            # Cạnh trái
            (l_orange, 140, -115, False, -54, 42),
            (l_green,  148, -72,  False, -52, 155),
            (l_ivy,    155, -95,  False, -56, 255),
            (l_green,  145, -68,  True,  -54, 365),
            (l_green,  140, -108, False, -54, 465),
            (l_green,  145, -72,  True,  -52, 555),

            # Cạnh phải
            (l_orange, 140, 112, False, WIN_W - 96, 48),
            (l_ivy,    155, 85,  False, WIN_W - 98, 145),
            (l_orange, 138, 108, True,  WIN_W - 92, 235),
            (l_green,  150, 68,  False, WIN_W - 96, 325),
            (l_orange, 138, 114, True,  WIN_W - 92, 425),
            (l_green,  142, 74,  False, WIN_W - 94, 515),
            (l_green,  150, 65,  True,  WIN_W - 98, 565),
        ]
        result = []
        for src, sz, ang, fx, lx, ly in specs:
            result.append((make_leaf(src, sz, ang, fx), lx, ly))
        return result

    def _rebuild_shell(self):
        _, skin_val = SHELL_BACKGROUNDS[self.shell_idx]
        if skin_val == "CLASSIC_FRONT":
            self.use_classic_front = True
        else:
            self.use_classic_front = False
            self.shell_surf, self.shell_btn_surfs = build_dom_shell_surface(
                skin_val, self.shell_w, self.shell_h
            )

    def _create_striped_surface(self, w: int, h: int, c1: tuple, c2: tuple) -> pygame.Surface:
        surf = pygame.Surface((w, h))
        surf.fill(c1)
        stripe_w = 12
        for offset in range(-h, w + h, stripe_w * 2):
            pts = [(offset, 0), (offset + stripe_w, 0), (offset + stripe_w - h, h), (offset - h, h)]
            pygame.draw.polygon(surf, c2, pts)
        return surf

    def show_toast(self, text: str, duration: float = 2.0):
        self.toast_text = text.upper()
        self.toast_timer = duration

    def push_menu(self, new_state: str):
        if self.menu_state:
            self.menu_stack.append((self.menu_state, self.cursor_idx, self.slider_idx))
        self.menu_state = new_state
        self.cursor_idx = 0
        self.slider_idx = 0

    def pop_menu(self):
        if self.menu_stack:
            prev_state, prev_cur, prev_sld = self.menu_stack.pop()
            self.menu_state = prev_state
            self.cursor_idx = prev_cur
            self.slider_idx = prev_sld
        else:
            self.menu_state = None
            if self.pet.scene == "activity_carousel":
                self.pet.scene = "home"

    def close_all_menus(self):
        self.menu_stack.clear()
        self.menu_state = None

    def get_current_sky(self) -> pygame.Surface:
        hour = datetime.datetime.now().hour
        if 6 <= hour < 12:
            return self.sky_images["morning"]
        elif 12 <= hour < 17:
            return self.sky_images["afternoon"]
        elif 17 <= hour < 20:
            return self.sky_images["evening"]
        return self.sky_images["night"]

    # =========================================================================
    # ĐIỀU KHIỂN 3 NÚT VỎ MÁY (A: TRÁI, B: GIỮA, C: PHẢI) & CHUỘT TRONG LCD
    # =========================================================================
    def press_button_a(self):
        self.pressed_shell_btn = 0
        self.pressed_timer = 0.15
        self.sound.play("click")

        if self.pet.scripted_mode:
            return

        if self.menu_state == "welcome_back":
            self.close_all_menus()
            return

        if self.menu_state is None:
            if self.pet.scene != "home":
                self.pet.scene = "home"
                self.pet.active_npc = None
            else:
                self.push_menu("main_grid")
        elif self.menu_state == "main_grid":
            self.cursor_idx = (self.cursor_idx + 1) % len(MAIN_GRID_ITEMS)
        elif self.menu_state == "activity_carousel":
            self.activity_idx = (self.activity_idx + 1) % len(OUTSIDE_ACTIVITIES)
        elif self.menu_state in ("slider_food", "slider_snack", "slider_item", "slider_acc", "slider_furn", "slider_room", "slider_seed", "slider_collection"):
            items = self._get_slider_data(self.menu_state)
            if items:
                self.slider_idx = (self.slider_idx + 1) % len(items)
        elif self.menu_state == "social_media":
            self.post_idx = (self.post_idx + 1) % len(SOCIAL_POSTS)
        elif self.menu_state == "minigame":
            if self.mg_type == "falling":
                self.mg_basket_x = max(8.0, self.mg_basket_x - 14.0)
            else:
                self.cursor_idx = (self.cursor_idx + 1) % 3
        else:
            options = self._get_list_options(self.menu_state)
            if options:
                self.cursor_idx = (self.cursor_idx + 1) % len(options)

    def press_button_b(self):
        self.pressed_shell_btn = 1
        self.pressed_timer = 0.15
        self.sound.play("confirm")

        if self.pet.scripted_mode:
            return

        if self.menu_state == "welcome_back":
            self.close_all_menus()
            return

        if self.menu_state is None:
            if self.pet.scene == "backyard" and self.pet.has_dig_spot:
                self.pet.has_dig_spot = False
                self.pet.gold += 45
                self.pet.spawn_arrows(4)
                self.show_toast("ĐÀO ĐƯỢC KHO BÁU +45$!")
            elif self.pet.scene == "garden":
                self.push_menu("garden_actions")
            elif self.pet.scene != "home":
                self.pet.scene = "home"
                self.pet.active_npc = None
            else:
                self.push_menu("main_grid")
        elif self.menu_state == "main_grid":
            chosen = MAIN_GRID_ITEMS[self.cursor_idx]["id"]
            self._open_main_grid_item(chosen)
        elif self.menu_state == "activity_carousel":
            self._enter_outdoor_activity(OUTSIDE_ACTIVITIES[self.activity_idx]["id"])
        elif self.menu_state in ("slider_food", "slider_snack", "slider_item", "slider_acc", "slider_furn", "slider_room", "slider_seed", "slider_collection"):
            self._accept_slider_item(self.menu_state)
        elif self.menu_state == "social_media":
            post = SOCIAL_POSTS[self.post_idx]
            if not post["liked"]:
                post["liked"] = True
                post["likes"] += 1
                self.pet.happiness = min(100.0, self.pet.happiness + 10.0)
                self.show_toast("ĐÃ THẢ TIM BÀI VIẾT!")
        elif self.menu_state in ("stats_bars", "profile_view", "family_tree", "leaderboard"):
            self.pop_menu()
        elif self.menu_state == "minigame":
            if self.mg_type == "guess":
                self._check_guess_choice(self.cursor_idx)
        else:
            options = self._get_list_options(self.menu_state)
            if options and 0 <= self.cursor_idx < len(options):
                _, fn = options[self.cursor_idx]
                fn()

    def press_button_c(self):
        self.pressed_shell_btn = 2
        self.pressed_timer = 0.15
        self.sound.play("cancel")

        if self.pet.scripted_mode:
            self.pet.scripted_mode = None
            self.pet.scene = "home"
            self.pet.set_state("idle")
            return

        if self.menu_state == "welcome_back":
            self.close_all_menus()
            return

        if self.menu_state is None:
            if self.pet.scene != "home":
                self.pet.scene = "home"
                self.pet.active_npc = None
            else:
                self.pet.pet_stroke()
        elif self.menu_state == "minigame":
            if self.mg_type == "falling":
                self.mg_basket_x = min(72.0, self.mg_basket_x + 14.0)
            else:
                self.close_all_menus()
                self.pet.scene = "home"
        else:
            self.pop_menu()

    def _open_main_grid_item(self, item_id: str):
        if item_id == "back":
            self.close_all_menus()
        elif item_id == "stats":
            self.push_menu("stats_menu")
        elif item_id == "feeding":
            self.push_menu("feeding_menu")
        elif item_id == "bath":
            self.push_menu("bath_menu")
        elif item_id == "care":
            self.push_menu("care_menu")
        elif item_id == "activity":
            self.pet.scene = "activity_carousel"
            self.push_menu("activity_carousel")
        elif item_id == "stuff":
            self.push_menu("stuff_menu")
        elif item_id == "phone":
            self.push_menu("phone_menu")
        elif item_id == "settings":
            self.push_menu("settings_menu")

    # =========================================================================
    # DANH SÁCH CÁC MENU CON CHUẨN HANDLERS.JS CỦA TAMAWEB (BẢN TIẾNG VIỆT)
    # =========================================================================
    def _get_list_options(self, state: str) -> list[tuple[str, callable]]:
        if state == "stats_menu":
            return [
                ("CHỈ SỐ & KỸ NĂNG", lambda: self.push_menu("stats_bars")),
                ("HỒ SƠ THÚ CƯNG", lambda: self.push_menu("profile_view")),
                (f"BỘ SƯU TẬP ({len(self.pet.unlocked_characters)})", lambda: self.push_menu("slider_collection")),
                ("CÂY GIA PHẢ", lambda: self.push_menu("family_tree")),
                ("QUAY LẠI", self.pop_menu),
            ]
        elif state == "feeding_menu":
            return [
                ("MÓN ĂN CHÍNH", lambda: self.push_menu("slider_food")),
                ("BÁNH KẸO & THUỐC", lambda: self.push_menu("slider_snack")),
                ("VÀO BẾP NẤU ĂN", self._start_cooking_menu),
                ("QUAY LẠI", self.pop_menu),
            ]
        elif state == "cook_menu":
            ing_list = [
                ("bread", "BÁNH MÌ"),
                ("milk", "SỮA TƯƠI"),
                ("tomato", "CÀ CHUA"),
                ("cabbage", "BẮP CẢI"),
                ("potato", "KHOAI TÂY"),
                ("fish dish", "CÁ TƯƠI"),
            ]
            rows = []
            for ing_id, ing_vn in ing_list:
                rows.append((f"+ {ing_vn}", lambda i=ing_vn: self._pick_cook_ingredient(i)))
            rows.append(("QUAY LẠI", self.pop_menu))
            return rows
        elif state == "bath_menu":
            return [
                ("TẮM BỒN XÀ PHÒNG", self._act_bath),
                ("ĐI VỆ SINH", self._act_toilet),
                ("ĐÁNH RĂNG SẠCH", self._act_brush_teeth),
                ("HÚT BỤI DỌN PHÒNG", self._act_clean_room),
                ("QUAY LẠI", self.pop_menu),
            ]
        elif state == "care_menu":
            sleep_lbl = "ĐÁNH THỨC DẬY" if self.pet.is_sleeping else "CHO ĐI NGỦ"
            return [
                ("DẠY DỖ / VUỐT VE", lambda: self.push_menu("discipline_menu")),
                ("NHIỆM VỤ HÀNG NGÀY", lambda: self.push_menu("missions_menu")),
                (sleep_lbl, self._act_toggle_sleep),
                ("RA SÂN SAU CHƠI", self._act_go_backyard),
                ("VƯỜN TRỒNG CÂY", self._act_go_garden),
                ("XEM ĐIỀU BÉ MUỐN", self._act_show_want),
                ("QUAY LẠI", self.pop_menu),
            ]
        elif state == "discipline_menu":
            return [
                ("KHEN NGỢI BÉ", self._act_praise),
                ("NHẮC NHỞ / LA MẮNG", self._act_scold),
                ("XOA ĐẦU ÂU YẾM", self._act_pet_stroke),
                ("GỬI ÔNG BÀ CHĂM", self._act_go_parents),
                ("QUAY LẠI", self.pop_menu),
            ]
        elif state == "missions_menu":
            rows = []
            for idx, m in enumerate(self.pet.missions):
                status = "XONG!" if m["claimed"] else f"{m['progress']}/{m['goal']} (+{m['reward']}$)"
                rows.append((f"{m['title']} {status}", lambda i=idx: self._claim_mission(i)))
            rows.append(("QUAY LẠI", self.pop_menu))
            return rows
        elif state == "garden_actions":
            return [
                ("TƯỚI NƯỚC TẤT CẢ", self._act_water_garden),
                ("THU HOẠCH CÂY CHÍN", self._act_harvest_garden),
                ("GIEO HẠT GIỐNG MỚI", lambda: self.push_menu("slider_seed")),
                ("VỀ NHÀ", self._act_return_home),
            ]
        elif state == "stuff_menu":
            return [
                ("ĐỒ CHƠI GIẢI TRÍ", lambda: self.push_menu("slider_item")),
                ("PHỤ KIỆN THỜI TRANG", lambda: self.push_menu("slider_acc")),
                ("NỘI THẤT PHÒNG", lambda: self.push_menu("slider_furn")),
                ("ĐỔI NỀN PHÒNG", lambda: self.push_menu("slider_room")),
                ("XƯỞNG CHẾ TẠO", lambda: self.push_menu("craft_menu")),
                ("QUAY LẠI", self.pop_menu),
            ]
        elif state == "craft_menu":
            return [
                ("PHÒNG NGHỆ THUẬT (HOA)", lambda: self._craft_item("room", "PHÒNG NGHỆ THUẬT", "resources/img/background/house/c_01.png")),
                ("MŨ CẦU VỒNG (HOA)", lambda: self._craft_item("acc", "rainbow hat", "resources/img/accessory/rainbow_hat_01.png")),
                ("SOFA ĐÁM MÂY (TRE)", lambda: self._craft_item("furn", "sofa_cloud", "resources/img/furniture/sofa_cloud.png")),
                ("ĐÈN MẶT TRỜI (TRE)", lambda: self._craft_item("furn", "lamp_sun", "resources/img/furniture/lamp_sun.png")),
                ("QUAY LẠI", self.pop_menu),
            ]
        elif state == "phone_menu":
            return [
                ("ĐÁM MÂY & XẾP HẠNG", lambda: self.push_menu("hubchi_menu")),
                ("BẠN BÈ & KẾT HÔN", lambda: self.push_menu("friends_menu")),
                ("MẠNG XÃ HỘI TAMAGRAM", lambda: self.push_menu("social_media")),
                ("MUA SẮM GIAO TẬN NƠI", lambda: self.push_menu("mall_menu")),
                ("VÉ CÀO MAY MẮN", self._act_scratch_card),
                ("QUAY LẠI", self.pop_menu),
            ]
        elif state == "hubchi_menu":
            return [
                ("LƯU LÊN ĐÁM MÂY", self._act_cloud_save),
                ("TẢI DỮ LIỆU ĐÁM MÂY", self._act_cloud_load),
                ("BẢNG XẾP HẠNG TOP", self._act_leaderboard),
                ("THĂM QUẢNG TRƯỜNG MẠNG", self._act_go_online_hub),
                ("QUAY LẠI", self.pop_menu),
            ]
        elif state == "friends_menu":
            rows = []
            for idx, fr in enumerate(self.pet.friends):
                rows.append((f"{fr['name']} ({fr['affection']} TIM)", lambda i=idx: self._interact_friend(i)))
            rows.append(("QUAY LẠI", self.pop_menu))
            return rows
        elif state == "mall_menu":
            return [
                ("TIỆM ĐỒ CHƠI", lambda: self.push_menu("slider_item")),
                ("SHOP PHỤ KIỆN", lambda: self.push_menu("slider_acc")),
                ("SIÊU THỊ NỘI THẤT", lambda: self.push_menu("slider_furn")),
                ("CỬA HÀNG GIẤY DÁN TƯỜNG", lambda: self.push_menu("slider_room")),
                ("QUAY LẠI", self.pop_menu),
            ]
        elif state == "arcade_menu":
            return [
                ("GAME HỨNG THỨC ĂN", lambda: self._start_minigame("falling")),
                ("GAME ĐOÁN SỐ LỚN/NHỎ", lambda: self._start_minigame("guess")),
                ("VỀ NHÀ", self._act_return_home),
            ]
        elif state == "school_menu":
            return [
                (f"LỚP BIỂU CẢM ({int(self.pet.skill_expression)}Đ)", lambda: self._attend_school("expression")),
                (f"LỚP TƯ DUY ({int(self.pet.skill_logic)}Đ)", lambda: self._attend_school("logic")),
                (f"LỚP THỂ LỰC ({int(self.pet.skill_endurance)}Đ)", lambda: self._attend_school("endurance")),
                ("VỀ NHÀ", self._act_return_home),
            ]
        elif state == "work_menu":
            return [
                ("LÀM VĂN PHÒNG (+45$)", lambda: self._do_work("work", 45)),
                ("BÁN HÀNG CHỢ (+35$)", lambda: self._do_work("market", 35)),
                ("DẠY HỌC TRƯỜNG (+55$)", lambda: self._do_work("school", 55)),
                ("VỀ NHÀ", self._act_return_home),
            ]
        elif state == "settings_menu":
            snd_txt = "BẬT" if self.sound.enabled else "TẮT"
            shell_name, _ = SHELL_BACKGROUNDS[self.shell_idx]
            pat_name, _ = BACKGROUND_PATTERNS[self.pattern_idx]
            return [
                (f"VỎ: {shell_name[:12]}", self._act_cycle_shell),
                (f"NỀN: {pat_name[:12]}", self._act_cycle_pattern),
                (f"ÂM THANH: {snd_txt}", self._act_toggle_sound),
                ("ĐỔI NHÂN VẬT KHÁC", self._act_change_chara),
                ("TIẾN HÓA CẤP TIẾP", self._act_evolve),
                ("ĐĂNG XUẤT TÀI KHOẢN", self._logout_account),
                ("QUAY LẠI", self.pop_menu),
            ]
        return [("QUAY LẠI", self.pop_menu)]

    def _get_slider_data(self, state: str) -> list[dict]:
        if state == "slider_food":
            return [f for f in FOODS if f["type"] != "treat"]
        elif state == "slider_snack":
            return [f for f in FOODS if f["type"] == "treat"]
        elif state == "slider_item":
            return ITEMS
        elif state == "slider_acc":
            return ACCESSORIES
        elif state == "slider_furn":
            return FURNITURES
        elif state == "slider_room":
            return ROOM_BACKGROUNDS
        elif state == "slider_seed":
            return PLANTS
        elif state == "slider_collection":
            return [{"name": f"NHÂN VẬT #{i+1}", "image": p} for i, p in enumerate(self.pet.unlocked_characters)]
        return []

    def _accept_slider_item(self, state: str):
        items = self._get_slider_data(state)
        if not items:
            return
        cur = items[self.slider_idx % len(items)]

        if state in ("slider_food", "slider_snack"):
            ok, msg = self.pet.start_feed(cur)
            self.show_toast(msg)
            if ok:
                self.close_all_menus()
                self.backend.send_analytics("feed", {"food": cur["name"]})
        elif state == "slider_item":
            ok, msg = self.pet.start_play_item(cur)
            self.show_toast(msg)
            if ok:
                self.close_all_menus()
        elif state == "slider_acc":
            equipped = self.pet.toggle_accessory(cur["id"])
            self.show_toast(f"{'ĐÃ ĐEO' if equipped else 'ĐÃ THÁO'} {cur['name']}!")
            self.close_all_menus()
        elif state == "slider_furn":
            placed = self.pet.toggle_furniture(cur["id"])
            self.show_toast(f"{'ĐÃ ĐẶT' if placed else 'ĐÃ CẤT'} {cur['name']}!")
            self.close_all_menus()
        elif state == "slider_room":
            rtype = cur.get("type", "room")
            if rtype == "bathroom":
                self.pet.bathroom_bg = cur["image"]
            elif rtype == "kitchen":
                self.pet.kitchen_bg = cur["image"]
            else:
                self.pet.room_bg = cur["image"]
            self.show_toast(f"ĐÃ ĐỔI {cur['name']}!")
            self.close_all_menus()
        elif state == "slider_seed":
            for i in range(len(self.pet.garden_plots)):
                if self.pet.garden_plots[i] is None:
                    self.pet.garden_plots[i] = {
                        "plant_id": cur["id"],
                        "sprite": cur["sprite"],
                        "stage": 0,
                        "watered": True,
                        "timer": 0.0,
                    }
                    self.show_toast(f"ĐÃ TRỒNG {cur['name']}!")
                    self.pop_menu()
                    return
            self.show_toast("VƯỜN ĐÃ ĐẦY 4 Ô!")
        elif state == "slider_collection":
            self.pet.character_file = cur["image"]
            self.pet.spritesheet = SpriteSheet(
                cur["image"],
                STAGE_INFO[self.pet.stage]["size"],
                STAGE_INFO[self.pet.stage]["cols"],
                STAGE_INFO[self.pet.stage]["rows"],
            )
            self.show_toast("ĐÃ ĐỔI NHÂN VẬT!")
            self.close_all_menus()

    # =========================================================================
    # XỬ LÝ CÁC HOẠT ĐỘNG NGOÀI TRỜI (13 TOÀ NHÀ OUTSIDE_ACTIVITIES)
    # =========================================================================
    def _enter_outdoor_activity(self, act_id: str):
        self.pet.advance_mission("park")
        if act_id == "home":
            self.pet.scene = "home"
            self.close_all_menus()
        elif act_id == "mall":
            self.pet.scene = "mall"
            self.push_menu("mall_menu")
        elif act_id == "market":
            self.pet.scene = "market"
            self.push_menu("slider_seed")
        elif act_id == "arcade":
            self.pet.scene = "arcade"
            self.push_menu("arcade_menu")
        elif act_id == "getaways":
            self.pet.scene = "getaways"
            self.pet.happiness = 100.0
            self.pet.spawn_hearts(5)
            self.close_all_menus()
            self.show_toast("NGHỈ MÁT BÃI BIỂN!")
        elif act_id == "fortune":
            self.pet.scene = "fortune"
            self.pet.active_npc = {"name": "BÀ ĐỒNG BÓI", "sprite": "resources/img/character/chara_362b.png"}
            self.close_all_menus()
            next_st = STAGE_INFO[min(5, self.pet.stage + 1)]["name"]
            self.show_toast(f"SẮP LÊN: {next_st}!")
        elif act_id == "park":
            self.pet.scene = "park"
            friend = random.choice(self.pet.friends)
            friend["affection"] = min(100, friend["affection"] + 15)
            self.pet.active_npc = friend
            self.pet.happiness = min(100.0, self.pet.happiness + 20.0)
            self.pet.spawn_hearts(4)
            self.close_all_menus()
            self.show_toast(f"GẶP BẠN {friend['name']}!")
        elif act_id == "school":
            self.pet.scene = "school"
            self.pet.active_npc = {"name": "THẦY GIÁO", "sprite": NPC_CHARACTERS[0]}
            self.push_menu("school_menu")
        elif act_id == "hospital":
            self.close_all_menus()
            self.pet.start_clinic()
            self.show_toast("BÁC SĨ ĐÃ CHỮA KHỎI!")
        elif act_id == "restaurant":
            self.pet.scene = "restaurant"
            self.pet.active_npc = random.choice(self.pet.friends)
            self.pet.hunger = 100.0
            self.pet.happiness = min(100.0, self.pet.happiness + 25.0)
            self.pet.spawn_hearts(4)
            self.close_all_menus()
            self.show_toast("ĂN TỐI CÙNG BẠN BÈ!")
        elif act_id == "work":
            self.pet.scene = "work"
            self.push_menu("work_menu")
        elif act_id == "underworld":
            self.pet.scene = "underworld"
            self.pet.happiness = min(100.0, self.pet.happiness + 15.0)
            self.close_all_menus()
            self.show_toast("THÁM HIỂM ÂM PHỦ!")
        elif act_id == "post_office":
            self.pet.scene = "post_office"
            self.pet.gold += 20
            self.close_all_menus()
            self.show_toast("NHẬN THƯ QUÀ +20$!")

    # =========================================================================
    # CÁC HÀNH ĐỘNG CHĂM SÓC & TƯƠNG TÁC
    # =========================================================================
    def _act_return_home(self):
        self.pet.scene = "home"
        self.pet.scripted_mode = None
        self.pet.scripted_timer = 0.0
        self.pet.active_npc = None
        self.close_all_menus()

    def _start_cooking_menu(self):
        self.cook_sel = []
        self.push_menu("cook_menu")

    def _pick_cook_ingredient(self, ing_name: str):
        self.cook_sel.append(ing_name)
        if len(self.cook_sel) < 2:
            self.show_toast(f"ĐÃ THÊM {ing_name} (CHỌN 1 NỮA)")
            return
        cookables = [f for f in FOODS if f.get("recipe")]
        cooked_dish = random.choice(cookables) if cookables else FOODS[6]
        self.close_all_menus()
        ok, _ = self.pet.start_feed(cooked_dish, free_override=True)
        if ok:
            self.show_toast(f"NẤU XONG {cooked_dish['name']}!")

    def _act_bath(self):
        self.close_all_menus()
        self.pet.start_bath()

    def _act_toilet(self):
        self.close_all_menus()
        self.pet.start_toilet()

    def _act_brush_teeth(self):
        self.close_all_menus()
        self.pet.start_brush_teeth()

    def _act_clean_room(self):
        self.close_all_menus()
        self.pet.start_clean_room()

    def _act_toggle_sleep(self):
        self.close_all_menus()
        sleeping = self.pet.toggle_sleep()
        self.show_toast("CHÚC BÉ NGỦ NGON!" if sleeping else "CHÀO BUỔI SÁNG!")

    def _act_praise(self):
        self.close_all_menus()
        self.pet.praise()
        self.show_toast("ĐÃ KHEN NGỢI BÉ!")

    def _act_scold(self):
        self.close_all_menus()
        self.pet.scold()
        self.show_toast("ĐÃ NHẮC NHỞ BÉ!")

    def _act_pet_stroke(self):
        self.close_all_menus()
        self.pet.pet_stroke()

    def _act_go_backyard(self):
        self.close_all_menus()
        self.pet.scripted_mode = None
        self.pet.scripted_timer = 0.0
        self.pet.scene = "backyard"
        self.pet.bowl_has_treat = True
        self.pet.has_dig_spot = True
        self.pet.backyard_animal["sprite"] = random.choice(
            ["resources/img/animal/cat_01.png", "resources/img/animal/dog_01.png", "resources/img/animal/cat_04.png"]
        )
        self.show_toast("ĐANG Ở SÂN SAU!")

    def _act_go_garden(self):
        self.close_all_menus()
        self.pet.scripted_mode = None
        self.pet.scripted_timer = 0.0
        self.pet.scene = "garden"
        self.show_toast("VƯỜN CÂY NÔNG TRẠI!")

    def _act_water_garden(self):
        for plot in self.pet.garden_plots:
            if plot:
                plot["watered"] = True
                if plot["stage"] < 3:
                    plot["stage"] += 1
        self.pet.advance_mission("water")
        self.sound.play("clean")
        self.show_toast("ĐÃ TƯỚI NƯỚC CẢ VƯỜN!")
        self.pop_menu()

    def _act_harvest_garden(self):
        harvested = 0
        for i, plot in enumerate(self.pet.garden_plots):
            if plot and plot["stage"] >= 2:
                pid = plot["plant_id"]
                self.pet.inventory_harvest[pid] = self.pet.inventory_harvest.get(pid, 0) + 1
                self.pet.gold += 15
                self.pet.garden_plots[i] = None
                harvested += 1
        if harvested > 0:
            self.sound.play("complete")
            self.show_toast(f"THU HOẠCH {harvested} CÂY (+{harvested*15}$)!")
        else:
            self.show_toast("CHƯA CÓ CÂY CHÍN!")
        self.pop_menu()

    def _act_go_parents(self):
        self.close_all_menus()
        self.pet.scene = "parents"
        self.pet.active_npc = {"name": "ÔNG BÀ TAMA", "sprite": "resources/img/character/chara_379b.png"}
        self.pet.hunger = 100.0
        self.pet.happiness = 100.0
        self.show_toast("ÔNG BÀ ĐÃ CHĂM BÉ!")

    def _act_show_want(self):
        self.close_all_menus()
        self.pet.show_current_want()
        self.show_toast(f"BÉ THÍCH: {self.pet.current_want['name']}!")

    def _claim_mission(self, idx: int):
        m = self.pet.missions[idx]
        if m["claimed"]:
            self.show_toast("ĐÃ NHẬN THƯỞNG RỒI!")
        elif m["progress"] >= m["goal"]:
            m["claimed"] = True
            self.pet.gold += m["reward"]
            self.sound.play("complete")
            self.show_toast(f"NHẬN THƯỞNG +{m['reward']}$!")
        else:
            self.show_toast(f"TIẾN ĐỘ: {m['progress']}/{m['goal']}")

    def _craft_item(self, ctype: str, item_id: str, img_path: str):
        if ctype == "room":
            self.pet.room_bg = img_path
        elif ctype == "acc":
            if item_id not in self.pet.equipped_accessories:
                self.pet.equipped_accessories.append(item_id)
        elif ctype == "furn":
            if item_id not in self.pet.placed_furniture:
                self.pet.placed_furniture.append(item_id)
        self.sound.play("complete")
        self.show_toast("CHẾ TẠO THÀNH CÔNG!")
        self.close_all_menus()

    def _interact_friend(self, idx: int):
        fr = self.pet.friends[idx]
        fr["affection"] = min(100, fr["affection"] + 20)
        if fr["affection"] >= 100 and self.pet.stage >= 4:
            self.close_all_menus()
            self.pet.start_wedding(fr)
            self.show_toast(f"KẾT HÔN CÙNG {fr['name']}! ĐỜI {self.pet.generation+1}!")
        else:
            self.close_all_menus()
            self.pet.scene = "park"
            self.pet.active_npc = fr
            self.pet.spawn_hearts(4)
            self.show_toast(f"HẸN HÒ {fr['name']} ({fr['affection']} TIM)")

    def _act_scratch_card(self):
        prize = random.choice([25, 50, 75, 100])
        self.pet.gold += prize
        self.sound.play("complete")
        self.show_toast(f"TRÚNG VÉ CÀO +{prize}$!")

    def _attend_school(self, skill_type: str):
        sk_vn = {"expression": "BIỂU CẢM", "logic": "TƯ DUY", "endurance": "THỂ LỰC"}.get(skill_type, "KỸ NĂNG")
        if skill_type == "expression":
            self.pet.skill_expression = min(100.0, self.pet.skill_expression + 10.0)
        elif skill_type == "logic":
            self.pet.skill_logic = min(100.0, self.pet.skill_logic + 10.0)
        else:
            self.pet.skill_endurance = min(100.0, self.pet.skill_endurance + 10.0)
        self.pet.exp += 20
        self.pet.spawn_arrows(5)
        self.sound.play("complete")
        self.show_toast(f"+10 ĐIỂM {sk_vn}!")
        self.close_all_menus()

    def _do_work(self, work_scene: str, pay: int):
        self.pet.scene = work_scene
        self.pet.gold += pay
        self.pet.exp += 20
        self.pet.spawn_arrows(4)
        self.sound.play("complete")
        self.close_all_menus()
        self.show_toast(f"LÀM VIỆC NHẬN +{pay}$!")

    def _start_minigame(self, mg_type: str):
        self.mg_type = mg_type
        self.menu_state = "minigame"
        self.pet.scene = "arcade"
        self.pet.advance_mission("play")
        if mg_type == "falling":
            self.mg_basket_x = 40.0
            self.mg_score = 0
            self.mg_timer = 15.0
            self.mg_coins = []
            self.mg_spawn_tick = 0.0
        else:
            self.mg_secret_num = random.randint(1, 9)
            self.mg_score = 0
            self.mg_timer = 5
            self.mg_guess_msg = f"SỐ TIẾP LỚN HAY NHỎ HƠN {self.mg_secret_num}?"

    def _check_guess_choice(self, choice_idx: int):
        nxt = random.randint(1, 9)
        while nxt == self.mg_secret_num:
            nxt = random.randint(1, 9)
        won = (choice_idx == 0 and nxt < self.mg_secret_num) or (choice_idx == 1 and nxt > self.mg_secret_num)
        self.mg_secret_num = nxt
        self.mg_timer -= 1
        if won:
            self.mg_score += 20
            self.sound.play("complete")
            self.mg_guess_msg = f"ĐÚNG RỒI! SỐ {nxt}! (+20$)"
        else:
            self.sound.play("refuse")
            self.mg_guess_msg = f"TRẬT RỒI! LÀ SỐ {nxt}!"
        if self.mg_timer <= 0:
            self.pet.gold += self.mg_score
            self.pet.happiness = min(100.0, self.pet.happiness + 25.0)
            self.pet.scene = "home"
            self.close_all_menus()
            self.show_toast(f"THẮNG +{self.mg_score}$!")

    def _act_cloud_save(self):
        ok, _ = self.backend.save_pet(self.pet.to_dict())
        self.sound.play("complete" if ok else "refuse")
        self.show_toast("ĐÃ LƯU LÊN ĐÁM MÂY!" if ok else "ĐÃ LƯU TRÊN MÁY!")

    def _act_cloud_load(self):
        data = self.backend.load_pet()
        if data:
            self.pet.load_from_dict(data)
            self.sound.play("complete")
            self.show_toast("ĐÃ TẢI DỮ LIỆU!")
        else:
            self.show_toast("CHƯA CÓ BẢN LƯU!")

    def _act_leaderboard(self):
        self.backend.save_pet(self.pet.to_dict())
        self.leaderboard_rows = self.backend.get_leaderboard()
        self.push_menu("leaderboard")

    def _act_go_online_hub(self):
        self.close_all_menus()
        self.pet.scene = "online_hub"
        self.backend.save_pet(self.pet.to_dict())
        self.show_toast("ĐÃ KẾT NỐI QUẢNG TRƯỜNG!")

    def _act_cycle_shell(self):
        self.shell_idx = (self.shell_idx + 1) % len(SHELL_BACKGROUNDS)
        self._rebuild_shell()
        name, _ = SHELL_BACKGROUNDS[self.shell_idx]
        self.show_toast(name)

    def _act_cycle_pattern(self):
        self.pattern_idx = (self.pattern_idx + 1) % len(BACKGROUND_PATTERNS)
        name, path = BACKGROUND_PATTERNS[self.pattern_idx]
        self.bg_pattern = load_image(path)
        self.show_toast(name)

    def _act_toggle_sound(self):
        self.sound.enabled = not self.sound.enabled
        self.show_toast("BẬT ÂM THANH" if self.sound.enabled else "TẮT ÂM THANH")

    def _act_change_chara(self):
        self.pet.change_character_variant()
        self.show_toast(f"NHÂN VẬT #{self.pet.char_idx + 1}")

    def _act_evolve(self):
        self.pet.evolve_next()
        self.show_toast(f"LÊN CẤP: {STAGE_INFO[self.pet.stage]['name']}!")

    # =========================================================================
    # UPDATE LOOP
    # =========================================================================
    def update(self, dt: float):
        self.bg_scroll_x = (self.bg_scroll_x + dt * 14.0) % self.bg_pattern.get_width()
        self.bg_scroll_y = (self.bg_scroll_y + dt * 14.0) % self.bg_pattern.get_height()

        if self.pressed_timer > 0:
            self.pressed_timer = max(0.0, self.pressed_timer - dt)
            if self.pressed_timer == 0:
                self.pressed_shell_btn = -1

        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)

        if self.admin_notice_timer > 0:
            self.admin_notice_timer = max(0.0, self.admin_notice_timer - dt)
            if self.admin_notice_timer == 0:
                self.admin_notice_msg = ""

        self.auth_anim_tick += dt
        if not self.is_authenticated:
            if self.auth_in_progress:
                self.auth_in_progress_time += dt
                try:
                    res = self.backend.check_auth_response()
                    if res is not None:
                        self._on_auth_complete(res)
                    elif self.auth_in_progress_time > 15.0:
                        self.auth_in_progress = False
                        self.sound.play("refuse")
                        self.auth_msg = "MÁY CHỦ PHẢN HỒI CHẬM, VUI LÒNG THỬ LẠI!"
                        self.auth_msg_color = COLOR_RED
                except Exception as e:
                    print("check_auth_response error:", e)
                    self.auth_in_progress = False
                    self.sound.play("refuse")
                    self.auth_msg = "LỖI PHẢN HỒI XÁC THỰC!"
                    self.auth_msg_color = COLOR_RED
            return

        if self.is_admin_mode:
            fresh_dash = self.backend.poll_web_admin_dashboard()
            if fresh_dash:
                self.admin_dashboard = fresh_dash
                self.admin_stats = fresh_dash.get("stats") or self.admin_stats
                self.admin_accounts = fresh_dash.get("accounts") or self.admin_accounts
            return

        # Auto-save mỗi 15 giây giống AUTO_SAVE_INTERVAL_SECS trong App.js
        self.auto_save_timer += dt
        if self.auto_save_timer >= 15.0:
            self.auto_save_timer = 0.0
            self.backend.save_pet(self.pet.to_dict())

        if self.menu_state == "minigame" and self.mg_type == "falling":
            self._update_falling_minigame(dt)
            return

        self.pet.update(dt)

    def _update_falling_minigame(self, dt: float):
        self.mg_timer -= dt
        self.mg_spawn_tick += dt
        if self.mg_spawn_tick >= 0.45:
            self.mg_spawn_tick = 0.0
            self.mg_coins.append({
                "x": float(random.randint(8, 84)),
                "y": -6.0,
                "vy": random.uniform(36.0, 56.0),
                "sprite": random.choice([2, 515, 605, 974, 1024]),
            })

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self.mg_basket_x = max(6.0, self.mg_basket_x - 65.0 * dt)
        if keys[pygame.K_RIGHT]:
            self.mg_basket_x = min(74.0, self.mg_basket_x + 65.0 * dt)

        mx, my = pygame.mouse.get_pos()
        if self.lcd_rect.collidepoint(mx, my):
            rel_x = (mx - self.lcd_rect.x) / LCD_SCALE
            self.mg_basket_x = max(6.0, min(74.0, rel_x - 8.0))

        remaining = []
        for c in self.mg_coins:
            c["y"] += c["vy"] * dt
            if 66 <= c["y"] <= 86 and abs(c["x"] - (self.mg_basket_x + 8)) <= 14:
                self.mg_score += 10
                self.sound.play("click")
            elif c["y"] < 96:
                remaining.append(c)
        self.mg_coins = remaining

        if self.mg_timer <= 0:
            reward_gold = self.mg_score // 2
            self.pet.gold += reward_gold
            self.pet.happiness = min(100.0, self.pet.happiness + 25.0)
            self.pet.exp += 25
            self.pet.scene = "home"
            self.close_all_menus()
            self.sound.play("cheer_success")
            self.show_toast(f"THẮNG +{reward_gold}$!")
            self.backend.send_analytics("minigame_end", {"score": self.mg_score})

    # =========================================================================
    # RENDER GIAO DIỆN TAMAWEB 1:1
    # =========================================================================
    def draw(self):
        self.clickable_lcd_areas.clear()
        self.window_click_areas.clear()

        # 1. Nền ngoài #FFDEAD + họa tiết bg_pattern_01..04 cuộn chéo
        self.screen.fill(COLOR_BG_NAVAJO)
        pw, ph = self.bg_pattern.get_size()
        for y in range(-int(self.bg_scroll_y), WIN_H, ph):
            for x in range(-int(self.bg_scroll_x), WIN_W, pw):
                self.screen.blit(self.bg_pattern, (x, y))

        # 2. Tán lá trang trí viền cửa sổ
        for leaf_surf, lx, ly in self.leaves:
            self.screen.blit(leaf_surf, (lx, ly))

        # Nếu chưa đăng nhập -> Hiển thị giao diện Đăng Nhập / Đăng Ký bằng đồ họa Tamaweb
        if not self.is_authenticated:
            self._draw_auth_screen()
            pygame.display.flip()
            return

        # Nếu là Quản trị viên (admin) đang ở Trang Quản Lý Tài Khoản -> Hiển thị Trang Quản Trị
        if self.is_admin_mode and self.backend.user_id == "admin" and self.backend.role == "admin":
            self._draw_admin_screen()
            pygame.display.flip()
            return

        # Nếu Admin đang thử nghiệm trong game -> Hiển thị nút quay về Trang Quản Trị ở góc trên
        if self.backend.user_id == "admin" and self.backend.role == "admin":
            btn_back_adm = pygame.Rect((WIN_W - 260) // 2, 22, 260, 36)
            pygame.draw.rect(self.screen, (110, 65, 25), btn_back_adm.move(0, 3), border_radius=10)
            pygame.draw.rect(self.screen, COLOR_PURPLE_BACK, btn_back_adm, border_radius=10)
            pygame.draw.rect(self.screen, COLOR_BORDER, btn_back_adm, 2, border_radius=10)
            adm_lbl = self.font_xs.render("< VỀ TRANG QUẢN LÝ TÀI KHOẢN (ADMIN)", False, (255, 255, 255))
            self.screen.blit(adm_lbl, (btn_back_adm.centerx - adm_lbl.get_width() // 2, btn_back_adm.centery - adm_lbl.get_height() // 2))
            self.window_click_areas.append((btn_back_adm, self._enter_admin_dashboard))

        # 3. Vỏ trứng Tamagotchi (.dom-shell 320x400 hoặc Classic Front.png)
        if self.use_classic_front:
            cf_w, cf_h = self.classic_front_scaled.get_size()
            self.screen.blit(self.classic_front_scaled, ((WIN_W - cf_w) // 2, (WIN_H - cf_h) // 2))
        else:
            shadow_egg = pygame.Surface((self.shell_w + 16, self.shell_h + 16), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_egg, (90, 55, 25, 55), (8, 12, self.shell_w, self.shell_h))
            self.screen.blit(shadow_egg, (self.shell_x - 4, self.shell_y + 4))

            self.screen.blit(self.shell_surf, (self.shell_x, self.shell_y))

            logo_x = self.shell_x + (self.shell_w - self.logo_scaled.get_width()) // 2
            self.screen.blit(self.logo_scaled, (logo_x, self.shell_y + 38))

            # Viền .graphics-wrapper mềm mại
            bezel_surf = pygame.Surface((LCD_DISPLAY + 8, LCD_DISPLAY + 8), pygame.SRCALPHA)
            pygame.draw.rect(bezel_surf, (60, 40, 25, 45), (0, 0, LCD_DISPLAY + 8, LCD_DISPLAY + 8), border_radius=6)
            self.screen.blit(bezel_surf, (self.lcd_rect.x - 4, self.lcd_rect.y - 4))

            for idx, rect in enumerate(self.shell_btn_rects):
                offset_y = 2 if self.pressed_shell_btn == idx else 0
                self.screen.blit(self.shell_btn_surfs[idx], (rect.x, rect.y + offset_y))

        # 4. Vẽ màn hình LCD (96x96 -> 192x192)
        self._draw_lcd_world()
        self.screen.blit(self.lcd_display, self.lcd_rect.topleft)

        pygame.display.flip()

    def _draw_lcd_world(self):
        self.lcd_native.fill((0, 0, 0, 255))

        # Lớp 1: Bầu trời thực tế
        self.lcd_native.blit(self.get_current_sky(), (0, 0))

        # Lớp 2: Cảnh nền hiện tại
        if self.pet.scene == "home":
            self.lcd_native.blit(load_image(self.pet.room_bg), (0, 0))
        elif self.pet.scene == "kitchen":
            self.lcd_native.blit(load_image(self.pet.kitchen_bg), (0, 0))
        elif self.pet.scene == "bathroom":
            self.lcd_native.blit(load_image(self.pet.bathroom_bg), (0, 0))
        elif self.pet.scene == "activity_carousel":
            # Vẽ mặt đất ngoài trời + toà nhà đang chọn (activity_building_*.png) giống Activities.goToActivities()
            self.lcd_native.blit(self.scene_bgs["activities_base"], (0, 0))
            b_info = OUTSIDE_ACTIVITIES[self.activity_idx % len(OUTSIDE_ACTIVITIES)]
            b_img = load_image(b_info["image"], season="spring")
            self.lcd_native.blit(b_img, (0, 0))
        else:
            bg = self.scene_bgs.get(self.pet.scene, load_image(self.pet.room_bg))
            self.lcd_native.blit(bg, (0, 0))

        # Lớp 3: Nhân vật Pet / Minigame
        if self.menu_state == "minigame" and self.mg_type == "falling":
            self._draw_falling_minigame_native()
        else:
            self.pet.draw(self.lcd_native)

        # Phóng đại 2x sắc nét lên 192x192
        pygame.transform.scale(self.lcd_native, (LCD_DISPLAY, LCD_DISPLAY), self.lcd_display)

        # Lớp 4: Bàn tay vuốt ve (tap_01.png) khi đang petting
        if self.pet.scripted_mode == "petting":
            hx = int((self.pet.x + 4) * LCD_SCALE + math.sin(self.pet.flip_tick * 14) * 10)
            hy = int((self.pet.y - 6) * LCD_SCALE)
            self.lcd_display.blit(self.tap_hand_img, (hx, hy))

        # Lớp 5: Nút nhỏ trên đỉnh khi đang ở ngoài sân / công viên / nhà hàng / vườn cây
        if self.menu_state is None and self.pet.scene != "home" and not self.pet.scripted_mode:
            top_bar = pygame.Rect(6, 4, LCD_DISPLAY - 12, 20)
            pygame.draw.rect(self.lcd_display, COLOR_SURFACE, top_bar, border_radius=6)
            pygame.draw.rect(self.lcd_display, COLOR_BORDER, top_bar, 2, border_radius=6)
            scene_vn = {
                "backyard": "SÂN SAU",
                "garden": "VƯỜN CÂY",
                "park": "CÔNG VIÊN",
                "restaurant": "NHÀ HÀNG",
                "getaways": "BÃI BIỂN",
                "fortune": "TIỆM BÓI",
                "underworld": "ÂM PHỦ",
                "post_office": "BƯU ĐIỆN",
                "parents": "NHÀ ÔNG BÀ",
                "online_hub": "QUẢNG TRƯỜNG",
            }.get(self.pet.scene, self.pet.scene.upper())
            lbl_str = "NHẤP ĐÀO KHO BÁU / VỀ NHÀ" if (self.pet.scene == "backyard" and self.pet.has_dig_spot) else f"{scene_vn} (NHẤP -> VỀ NHÀ)"
            lbl = self.font_xs.render(lbl_str, False, COLOR_TEXT_ORANGE)
            self.lcd_display.blit(lbl, (top_bar.centerx - lbl.get_width() // 2, top_bar.centery - lbl.get_height() // 2))

            if self.pet.scene == "garden":
                g_btns = [
                    ("TƯỚI CÂY", self._act_water_garden),
                    ("THU HOẠCH", self._act_harvest_garden),
                    ("GIEO HẠT", lambda: self.push_menu("slider_seed")),
                ]
                for gi, (g_lbl, g_fn) in enumerate(g_btns):
                    gr = pygame.Rect(6 + gi * 61, LCD_DISPLAY - 26, 58, 22)
                    pygame.draw.rect(self.lcd_display, COLOR_SURFACE_ACTIVE, gr, border_radius=5)
                    pygame.draw.rect(self.lcd_display, COLOR_BORDER, gr, 2, border_radius=5)
                    gt = self.font_xs.render(g_lbl, False, COLOR_TEXT_ORANGE)
                    self.lcd_display.blit(gt, (gr.centerx - gt.get_width() // 2, gr.centery - gt.get_height() // 2))
                    self.clickable_lcd_areas.append((gr, g_fn))

        # Lớp 6: Vẽ các Menu bên trong LCD
        if self.menu_state == "welcome_back":
            self._draw_ui_welcome_back()
        elif self.menu_state == "main_grid":
            self._draw_ui_main_grid()
        elif self.menu_state == "activity_carousel":
            self._draw_ui_activity_carousel()
        elif self.menu_state == "stats_bars":
            self._draw_ui_stats_bars()
        elif self.menu_state == "profile_view":
            self._draw_ui_profile()
        elif self.menu_state == "family_tree":
            self._draw_ui_family_tree()
        elif self.menu_state == "leaderboard":
            self._draw_ui_leaderboard()
        elif self.menu_state == "social_media":
            self._draw_ui_social_media()
        elif self.menu_state == "minigame" and self.mg_type == "guess":
            self._draw_ui_guess_game()
        elif self.menu_state in ("slider_food", "slider_snack", "slider_item", "slider_acc", "slider_furn", "slider_room", "slider_seed", "slider_collection"):
            self._draw_ui_slider(self.menu_state)
        elif self.menu_state is not None and self.menu_state != "minigame":
            self._draw_ui_generic_list(self.menu_state, self._get_list_options(self.menu_state))

        # Lớp 7: Toast popup trong LCD
        if self.toast_timer > 0 and self.toast_text:
            toast_rect = pygame.Rect(8, LCD_DISPLAY - 26, LCD_DISPLAY - 16, 22)
            pygame.draw.rect(self.lcd_display, COLOR_SURFACE, toast_rect, border_radius=6)
            pygame.draw.rect(self.lcd_display, COLOR_BORDER, toast_rect, 2, border_radius=6)
            ts = self.font_xs.render(self.toast_text, False, COLOR_TEXT_ORANGE)
            self.lcd_display.blit(ts, (toast_rect.centerx - ts.get_width() // 2, toast_rect.centery - ts.get_height() // 2))

    def _draw_falling_minigame_native(self):
        cs = STAGE_INFO[self.pet.stage]["size"]
        self.pet.spritesheet.draw_with_breath(
            self.lcd_native, 2, int(self.mg_basket_x), 96 - cs - 6, inverted=False, upper_offset_y=0
        )
        for c in self.mg_coins:
            f_surf = pygame.transform.scale(self.pet.foods_sheet.get_frame(c["sprite"]), (12, 12))
            self.lcd_native.blit(f_surf, (int(c["x"] - 6), int(c["y"] - 6)))

    def _draw_pointer(self, x: int, y: int):
        """Vẽ bàn tay trỏ pointer_right.png nhấp nhô chuẩn styles.css dòng 595"""
        anim_x = int(math.sin(self.pet.flip_tick * 10) * 2)
        self.lcd_display.blit(self.pointer_img, (x + anim_x, y - 9))

    def _draw_ui_welcome_back(self):
        """Vẽ hộp thoại Chào mừng trong màn hình LCD giống hệt ảnh chuẩn Tamaweb"""
        self.lcd_display.blit(self.striped_bg_b, (0, 0))
        pygame.draw.rect(self.lcd_display, COLOR_BORDER, (0, 0, LCD_DISPLAY, LCD_DISPLAY), 3, border_radius=6)

        msg_card = pygame.Rect(14, 16, LCD_DISPLAY - 28, 122)
        pygame.draw.rect(self.lcd_display, COLOR_SURFACE_SHADOW, msg_card.move(0, 3), border_radius=10)
        pygame.draw.rect(self.lcd_display, COLOR_SURFACE, msg_card, border_radius=10)
        pygame.draw.rect(self.lcd_display, COLOR_BORDER, msg_card, 2, border_radius=10)

        lines = [
            "CHÀO MỪNG TRỞ LẠI!",
            f"{self.pet.name.upper()}",
            "ĐÃ RẤT NHỚ BẠN",
            "TRONG THỜI GIAN",
            "BẠN VẮNG MẶT!",
        ]
        for idx, line in enumerate(lines):
            l_surf = self.font_xs.render(line, False, COLOR_TEXT_ORANGE)
            self.lcd_display.blit(
                l_surf,
                (msg_card.centerx - l_surf.get_width() // 2, msg_card.y + 14 + idx * 20),
            )

        ok_btn = pygame.Rect(10, LCD_DISPLAY - 40, LCD_DISPLAY - 20, 28)
        pygame.draw.rect(self.lcd_display, COLOR_SURFACE_SHADOW, ok_btn.move(0, 3), border_radius=8)
        pygame.draw.rect(self.lcd_display, COLOR_SURFACE, ok_btn, border_radius=8)
        pygame.draw.rect(self.lcd_display, COLOR_BORDER, ok_btn, 2, border_radius=8)
        ok_txt = self.font_xs.render("OK", False, COLOR_TEXT_ORANGE)
        self.lcd_display.blit(ok_txt, (ok_btn.x + 12, ok_btn.centery - ok_txt.get_height() // 2))

        def dismiss_welcome():
            self.sound.play("confirm")
            self.close_all_menus()

        self.clickable_lcd_areas.append((pygame.Rect(0, 0, LCD_DISPLAY, LCD_DISPLAY), dismiss_welcome))

    def _draw_ui_main_grid(self):
        """
        Vẽ Menu 3x3 chuẩn .generic-grid-container & .grid-item của Tamaweb (styles.css dòng 917-941):
        9 hình tròn 55x55 màu pastel (--mm-clr-1..8 + #3d00ff) + icon trắng + bàn tay pointer_right.png
        """
        self.lcd_display.blit(self.striped_bg_a, (0, 0))
        cell_size = LCD_DISPLAY // 3  # 64x64

        for idx, item in enumerate(MAIN_GRID_ITEMS):
            r = idx // 3
            c = idx % 3
            cx = c * cell_size + cell_size // 2
            cy = r * cell_size + cell_size // 2
            rect = pygame.Rect(c * cell_size + 4, r * cell_size + 4, cell_size - 8, cell_size - 8)
            is_sel = (idx == self.cursor_idx)

            # Hình tròn 54x54 chuẩn .grid-item:before (width: 55px; height: 55px; border-radius: 100px)
            pygame.draw.circle(self.lcd_display, (255, 229, 202), (cx, cy + 1), 28)
            pygame.draw.circle(self.lcd_display, item["color"], (cx, cy), 26)

            if is_sel:
                pygame.draw.circle(self.lcd_display, (255, 255, 255), (cx, cy), 28, 3)

            draw_grid_icon(self.lcd_display, item["icon"], cx, cy)

            if is_sel:
                self._draw_pointer(rect.x - 4, cy)

            def make_cb(i=idx, item_id=item["id"]):
                def _cb():
                    self.cursor_idx = i
                    self.sound.play("confirm")
                    self._open_main_grid_item(item_id)
                return _cb

            self.clickable_lcd_areas.append((rect, make_cb()))

    def _draw_ui_activity_carousel(self):
        """
        Vẽ giao diện chọn 13 tòa nhà ngoài trời chuẩn Activities.goToActivities() (Activities.js dòng 2126-2155):
        Banner tên tòa nhà + #số ở trên, mũi tên < > ở giữa, nút HOME (đỏ) và ENTER DOOR (xanh lá) ở dưới
        """
        act = OUTSIDE_ACTIVITIES[self.activity_idx % len(OUTSIDE_ACTIVITIES)]

        # Banner tên địa điểm trên đỉnh
        hdr = pygame.Rect(14, 6, LCD_DISPLAY - 28, 32)
        pygame.draw.rect(self.lcd_display, COLOR_SURFACE, hdr, border_radius=8)
        pygame.draw.rect(self.lcd_display, COLOR_BORDER, hdr, 2, border_radius=8)
        t1 = self.font_xs.render(act["name"], False, COLOR_TEXT_ORANGE)
        t2 = self.font_xs.render(f"#{self.activity_idx + 1} / {len(OUTSIDE_ACTIVITIES)}", False, COLOR_BORDER)
        self.lcd_display.blit(t1, (hdr.centerx - t1.get_width() // 2, hdr.y + 4))
        self.lcd_display.blit(t2, (hdr.centerx - t2.get_width() // 2, hdr.y + 17))

        # 2 nút tròn < và > ở hai bên
        btn_left = pygame.Rect(6, 82, 32, 32)
        btn_right = pygame.Rect(LCD_DISPLAY - 38, 82, 32, 32)
        for r_btn, sym in [(btn_left, "<"), (btn_right, ">")]:
            pygame.draw.circle(self.lcd_display, COLOR_SURFACE, r_btn.center, 15)
            pygame.draw.circle(self.lcd_display, COLOR_BORDER, r_btn.center, 15, 2)
            s_surf = self.font_md.render(sym, False, COLOR_TEXT_ORANGE)
            self.lcd_display.blit(s_surf, (r_btn.centerx - s_surf.get_width() // 2, r_btn.centery - s_surf.get_height() // 2))

        # 2 nút dưới đáy: VỀ NHÀ (#cancel) và VÀO (#apply)
        btn_home = pygame.Rect(8, LCD_DISPLAY - 32, 54, 26)
        btn_enter = pygame.Rect(LCD_DISPLAY - 62, LCD_DISPLAY - 32, 54, 26)

        pygame.draw.rect(self.lcd_display, (255, 195, 195), btn_home, border_radius=7)
        pygame.draw.rect(self.lcd_display, (163, 0, 0), btn_home, 2, border_radius=7)
        h_txt = self.font_xs.render("VỀ NHÀ", False, (163, 0, 0))
        self.lcd_display.blit(h_txt, (btn_home.centerx - h_txt.get_width() // 2, btn_home.centery - h_txt.get_height() // 2))

        pygame.draw.rect(self.lcd_display, (15, 133, 0), btn_enter, border_radius=7)
        pygame.draw.rect(self.lcd_display, (255, 255, 255), btn_enter, 2, border_radius=7)
        e_txt = self.font_xs.render("VÀO", False, (255, 255, 255))
        self.lcd_display.blit(e_txt, (btn_enter.centerx - e_txt.get_width() // 2, btn_enter.centery - e_txt.get_height() // 2))

        def prev_act():
            self.activity_idx = (self.activity_idx - 1) % len(OUTSIDE_ACTIVITIES)
            self.sound.play("click")

        def next_act():
            self.activity_idx = (self.activity_idx + 1) % len(OUTSIDE_ACTIVITIES)
            self.sound.play("click")

        self.clickable_lcd_areas.append((btn_left, prev_act))
        self.clickable_lcd_areas.append((btn_right, next_act))
        self.clickable_lcd_areas.append((btn_home, self._act_return_home))
        self.clickable_lcd_areas.append((btn_enter, self.press_button_b))

    def _draw_ui_generic_list(self, state_key: str, options: list[tuple[str, callable]]):
        """Vẽ danh sách .generic-list-container với nút .generic-btn.stylized và con trỏ pointer_right.png"""
        self.lcd_display.blit(self.striped_bg_b, (0, 0))

        # Tự động cuộn cửa sổ 5 mục nếu danh sách dài hơn 5 mục
        max_vis = 5
        total = len(options)
        start_i = max(0, min(self.cursor_idx - 2, total - max_vis)) if total > max_vis else 0
        vis_options = options[start_i : start_i + max_vis]

        row_h = 30
        gap = 6
        y_top = 8
        for i_rel, (label, fn) in enumerate(vis_options):
            real_idx = start_i + i_rel
            rect = pygame.Rect(8, y_top + i_rel * (row_h + gap), LCD_DISPLAY - 16, row_h)
            is_sel = (real_idx == self.cursor_idx)
            is_back = (label in ("BACK", "RETURN HOME", "QUAY LẠI", "VỀ NHÀ"))

            if is_back:
                bg_col = COLOR_PURPLE_BACK
                txt_col = (255, 255, 255)
                bdr_col = (30, 0, 140)
            else:
                bg_col = COLOR_SURFACE_ACTIVE if is_sel else COLOR_SURFACE
                txt_col = COLOR_TEXT_ORANGE
                bdr_col = COLOR_BORDER

            # Đổ bóng nút dưới đáy (border-bottom-width: 4px)
            pygame.draw.rect(self.lcd_display, bdr_col, rect.move(0, 2), border_radius=8)
            pygame.draw.rect(self.lcd_display, bg_col, rect, border_radius=8)
            pygame.draw.rect(self.lcd_display, bdr_col, rect, 2, border_radius=8)

            txt_surf = self.font_xs.render(label, False, txt_col)
            self.lcd_display.blit(txt_surf, (rect.x + 18, rect.centery - txt_surf.get_height() // 2))

            if is_sel:
                self._draw_pointer(rect.x - 4, rect.centery)

            def make_row_cb(r_i=real_idx, action=fn):
                def _cb():
                    self.cursor_idx = r_i
                    self.sound.play("confirm")
                    action()
                return _cb

            self.clickable_lcd_areas.append((rect, make_row_cb()))

    def _draw_ui_slider(self, state: str):
        """Vẽ trình chọn vật phẩm .generic-slider-container chuẩn Tamaweb (Đồ ăn, Đồ chơi, Phụ kiện, Nội thất, Hạt giống)"""
        self.lcd_display.blit(self.striped_bg_a, (0, 0))
        items = self._get_slider_data(state)
        if not items:
            return
        cur = items[self.slider_idx % len(items)]

        # Top slot trái (Số thứ tự) & phải (Vàng hiện có) chuẩn .top-slot
        slot_l = pygame.Rect(6, 4, 62, 18)
        slot_r = pygame.Rect(LCD_DISPLAY - 82, 4, 76, 18)
        for s_rect in (slot_l, slot_r):
            pygame.draw.rect(self.lcd_display, (255, 255, 255), s_rect, border_radius=5)
            pygame.draw.rect(self.lcd_display, COLOR_BORDER, s_rect, 1, border_radius=5)
        sl_txt = self.font_xs.render(f"#{self.slider_idx + 1}/{len(items)}", False, COLOR_TEXT_ORANGE)
        sr_txt = self.font_xs.render(f"${self.pet.gold}", False, COLOR_TEXT_ORANGE)
        self.lcd_display.blit(sl_txt, (slot_l.centerx - sl_txt.get_width() // 2, slot_l.centery - sl_txt.get_height() // 2))
        self.lcd_display.blit(sr_txt, (slot_r.centerx - sr_txt.get_width() // 2, slot_r.centery - sr_txt.get_height() // 2))

        # Khung .content.surface-stylized ở giữa
        card = pygame.Rect(38, 26, LCD_DISPLAY - 76, 124)
        pygame.draw.rect(self.lcd_display, COLOR_SURFACE, card, border_radius=10)
        pygame.draw.rect(self.lcd_display, COLOR_BORDER, card, 2, border_radius=10)

        # Lấy hình ảnh sprite của vật phẩm
        if state in ("slider_food", "slider_snack"):
            raw_img = self.pet.foods_sheet.get_frame(cur["sprite"])
            sub_txt = "MIỄN PHÍ" if cur.get("price", 0) == 0 else f"${cur.get('price', 10)} (+{cur.get('hunger', 15)} NO)"
        elif state == "slider_item":
            raw_img = self.pet.items_sheet.get_frame(cur["sprite"])
            sub_txt = f"+{cur.get('fun', 15)} VUI VẺ"
        elif state == "slider_seed":
            raw_img = self.pet.plants_sheet.get_frame(cur["sprite"] + 3)
            sub_txt = "TRỒNG VÀO VƯỜN"
        elif state == "slider_collection":
            sh = SpriteSheet(cur["image"], 32, 4, 4)
            raw_img = sh.get_frame(1)
            sub_txt = "ĐÃ MỞ KHÓA"
        else:
            raw_img = load_image(cur["image"])
            sub_txt = "ĐEO / BÀY TRÍ"

        icon_scaled = pygame.transform.scale(raw_img, (56, 56))
        self.lcd_display.blit(icon_scaled, (card.centerx - 28, card.y + 10))

        nm_surf = self.font_xs.render(cur["name"][:14], False, COLOR_TEXT_ORANGE)
        self.lcd_display.blit(nm_surf, (card.centerx - nm_surf.get_width() // 2, card.y + 74))

        sb_surf = self.font_xs.render(sub_txt[:16], False, COLOR_GREEN if "MIỄN PHÍ" in sub_txt else COLOR_BORDER)
        self.lcd_display.blit(sb_surf, (card.centerx - sb_surf.get_width() // 2, card.y + 96))

        # 2 nút tròn .slide-action trái & phải
        btn_left = pygame.Rect(4, 72, 30, 30)
        btn_right = pygame.Rect(LCD_DISPLAY - 34, 72, 30, 30)
        for r_btn, sym in [(btn_left, "<"), (btn_right, ">")]:
            pygame.draw.circle(self.lcd_display, COLOR_SURFACE, r_btn.center, 14)
            pygame.draw.circle(self.lcd_display, COLOR_BORDER, r_btn.center, 14, 2)
            s_surf = self.font_sm.render(sym, False, COLOR_TEXT_ORANGE)
            self.lcd_display.blit(s_surf, (r_btn.centerx - s_surf.get_width() // 2, r_btn.centery - s_surf.get_height() // 2))

        # 2 nút .actions-container dưới đáy: HỦY BỎ (#3d00ff) & CHỌN (#fff4e8)
        btn_cancel = pygame.Rect(8, LCD_DISPLAY - 34, 84, 28)
        btn_accept = pygame.Rect(100, LCD_DISPLAY - 34, 84, 28)

        pygame.draw.rect(self.lcd_display, COLOR_PURPLE_BACK, btn_cancel, border_radius=8)
        c_txt = self.font_xs.render("HỦY BỎ", False, (255, 255, 255))
        self.lcd_display.blit(c_txt, (btn_cancel.centerx - c_txt.get_width() // 2, btn_cancel.centery - c_txt.get_height() // 2))

        pygame.draw.rect(self.lcd_display, COLOR_BORDER, btn_accept.move(0, 2), border_radius=8)
        pygame.draw.rect(self.lcd_display, COLOR_SURFACE, btn_accept, border_radius=8)
        pygame.draw.rect(self.lcd_display, COLOR_BORDER, btn_accept, 2, border_radius=8)
        a_txt = self.font_xs.render("CHỌN", False, COLOR_TEXT_ORANGE)
        self.lcd_display.blit(a_txt, (btn_accept.centerx - a_txt.get_width() // 2, btn_accept.centery - a_txt.get_height() // 2))
        self._draw_pointer(btn_accept.x - 4, btn_accept.centery)

        def prev_item():
            self.slider_idx = (self.slider_idx - 1) % len(items)
            self.sound.play("click")

        def next_item():
            self.slider_idx = (self.slider_idx + 1) % len(items)
            self.sound.play("click")

        self.clickable_lcd_areas.append((btn_left, prev_item))
        self.clickable_lcd_areas.append((btn_right, next_item))
        self.clickable_lcd_areas.append((btn_cancel, self.press_button_c))
        self.clickable_lcd_areas.append((btn_accept, self.press_button_b))

    def _draw_ui_stats_bars(self):
        self.lcd_display.blit(self.striped_bg_b, (0, 0))
        card = pygame.Rect(6, 6, LCD_DISPLAY - 12, LCD_DISPLAY - 40)
        pygame.draw.rect(self.lcd_display, COLOR_SURFACE, card, border_radius=8)
        pygame.draw.rect(self.lcd_display, COLOR_BORDER, card, 2, border_radius=8)

        bars = [
            ("ĐỘ NO", self.pet.hunger),
            ("GIẤC NGỦ", self.pet.energy),
            ("VUI VẺ", self.pet.happiness),
            ("NGOAN", self.pet.discipline),
        ]
        y_pos = card.y + 8
        for name, val in bars:
            lbl = self.font_xs.render(name, False, COLOR_TEXT_ORANGE)
            self.lcd_display.blit(lbl, (card.x + 8, y_pos))
            bar_bg = pygame.Rect(card.x + 82, y_pos + 1, 88, 10)
            pygame.draw.rect(self.lcd_display, (235, 215, 195), bar_bg, border_radius=4)
            fill_w = int(86 * max(0.0, min(100.0, val)) / 100.0)
            if fill_w > 0:
                pygame.draw.rect(
                    self.lcd_display, COLOR_GREEN if val >= 35 else COLOR_RED,
                    (bar_bg.x + 1, bar_bg.y + 1, fill_w, 8), border_radius=3
                )
            pygame.draw.rect(self.lcd_display, COLOR_BORDER, bar_bg, 1, border_radius=4)
            y_pos += 20

        # 3 kỹ năng trường học (Expression, Logic, Endurance)
        sk_hdr = self.font_xs.render("KỸ NĂNG HỌC TẬP:", False, COLOR_PURPLE_BACK)
        self.lcd_display.blit(sk_hdr, (card.x + 8, y_pos + 4))
        sk_line = self.font_xs.render(
            f"CẢM:{int(self.pet.skill_expression)}  DUY:{int(self.pet.skill_logic)}  BỀN:{int(self.pet.skill_endurance)}",
            False, COLOR_TEXT_ORANGE
        )
        self.lcd_display.blit(sk_line, (card.x + 8, y_pos + 22))
        gold_line = self.font_xs.render(f"TIỀN: ${self.pet.gold}   ĐỜI: {self.pet.generation}", False, COLOR_GREEN)
        self.lcd_display.blit(gold_line, (card.x + 8, y_pos + 40))

        self._draw_bottom_back_btn()

    def _draw_ui_profile(self):
        self.lcd_display.blit(self.striped_bg_b, (0, 0))
        card = pygame.Rect(6, 6, LCD_DISPLAY - 12, LCD_DISPLAY - 40)
        pygame.draw.rect(self.lcd_display, COLOR_SURFACE, card, border_radius=8)
        pygame.draw.rect(self.lcd_display, COLOR_BORDER, card, 2, border_radius=8)

        # Avatar pet bên trái
        pet_icon = pygame.transform.scale(self.pet.spritesheet.get_frame(1), (40, 40))
        self.lcd_display.blit(pet_icon, (card.x + 10, card.y + 10))

        lines = [
            f"{self.pet.name}",
            f"CẤP: {STAGE_INFO[self.pet.stage]['name']}",
            f"ĐỜI {self.pet.generation} ({self.pet.gender})",
            f"TIỀN: ${self.pet.gold}",
            f"BẠN BÈ: {len(self.pet.friends)}",
            f"TUỔI: {int(self.pet.age_seconds // 60)}P {int(self.pet.age_seconds % 60)}G",
        ]
        y_pos = card.y + 10
        for i, line in enumerate(lines):
            x_pos = card.x + 56 if i < 2 else card.x + 12
            surf = self.font_xs.render(line, False, COLOR_TEXT_ORANGE)
            self.lcd_display.blit(surf, (x_pos, y_pos))
            y_pos += 21

        self._draw_bottom_back_btn()

    def _draw_ui_family_tree(self):
        self.lcd_display.blit(self.striped_bg_b, (0, 0))
        card = pygame.Rect(6, 6, LCD_DISPLAY - 12, LCD_DISPLAY - 40)
        pygame.draw.rect(self.lcd_display, COLOR_SURFACE, card, border_radius=8)
        pygame.draw.rect(self.lcd_display, COLOR_BORDER, card, 2, border_radius=8)

        title = self.font_xs.render(f"CÂY GIA PHẢ (ĐỜI {self.pet.generation})", False, COLOR_PURPLE_BACK)
        self.lcd_display.blit(title, (card.centerx - title.get_width() // 2, card.y + 6))

        if not self.pet.family_history:
            msg = self.font_xs.render("THẾ HỆ ĐẦU TIÊN (ĐỜI 1)!", False, COLOR_TEXT_ORANGE)
            msg2 = self.font_xs.render("KẾT HÔN BẠN BÈ ĐẠT 100 TIM", False, COLOR_BORDER)
            self.lcd_display.blit(msg, (card.centerx - msg.get_width() // 2, card.y + 52))
            self.lcd_display.blit(msg2, (card.centerx - msg2.get_width() // 2, card.y + 74))
        else:
            last_gen = self.pet.family_history[-1]
            p1 = SpriteSheet(last_gen["sprite"], 32, 4, 4).get_frame(1)
            p2 = SpriteSheet(last_gen["partner_sprite"], 32, 4, 4).get_frame(1)
            self.lcd_display.blit(p1, (card.x + 28, card.y + 26))
            pygame.draw.line(self.lcd_display, COLOR_PURPLE_BACK, (card.x + 62, card.y + 42), (card.x + 114, card.y + 42), 2)
            self.lcd_display.blit(p2, (card.x + 116, card.y + 26))
            pygame.draw.line(self.lcd_display, (255, 0, 198), (card.centerx, card.y + 42), (card.centerx, card.y + 82), 2)

        cur_icon = pygame.transform.scale(self.pet.spritesheet.get_frame(1), (32, 32))
        self.lcd_display.blit(cur_icon, (card.centerx - 16, card.y + 88))
        self._draw_bottom_back_btn()

    def _draw_ui_social_media(self):
        """Vẽ bài đăng mạng xã hội chuẩn .post-container (styles.css dòng 1268-1362)"""
        post = SOCIAL_POSTS[self.post_idx % len(SOCIAL_POSTS)]

        # Ảnh bài đăng ở nửa trên
        post_bg = self.scene_bgs["park"]
        self.lcd_display.blit(pygame.transform.scale(post_bg, (LCD_DISPLAY, 112)), (0, 0))
        author_sheet = SpriteSheet(post["sprite"], 32, 4, 4)
        author_img = pygame.transform.scale(author_sheet.get_frame(2), (64, 64))
        self.lcd_display.blit(author_img, (LCD_DISPLAY // 2 - 32, 36))

        # Thanh .post-header màu tím #3d00ff trên cùng
        pygame.draw.rect(self.lcd_display, COLOR_PURPLE_BACK, (0, 0, LCD_DISPLAY, 28))
        h_txt = self.font_xs.render(f"@{post['author']}", False, (255, 255, 255))
        self.lcd_display.blit(h_txt, (10, 8))

        # Khung .post-text màu trắng dưới đáy (tự động ngắt dòng theo từ)
        pygame.draw.rect(self.lcd_display, (255, 255, 255), (0, 108, LCD_DISPLAY, LCD_DISPLAY - 108))
        pygame.draw.line(self.lcd_display, COLOR_PURPLE_BACK, (0, 108), (LCD_DISPLAY, 108), 4)

        line1, line2 = "", ""
        for w in post["text"].split(" "):
            test_l = (line1 + " " + w).strip()
            if not line2 and self.font_xs.size(test_l)[0] <= LCD_DISPLAY - 16:
                line1 = test_l
            else:
                line2 = (line2 + " " + w).strip()
        l1 = self.font_xs.render(line1, False, (18, 0, 78))
        l2 = self.font_xs.render(line2, False, (18, 0, 78))
        self.lcd_display.blit(l1, (8, 116))
        self.lcd_display.blit(l2, (8, 132))

        # 3 nút: TIM, TIẾP (>), ĐÓNG (X)
        btn_like = pygame.Rect(8, LCD_DISPLAY - 30, 56, 24)
        btn_next = pygame.Rect(70, LCD_DISPLAY - 30, 56, 24)
        btn_back = pygame.Rect(132, LCD_DISPLAY - 30, 52, 24)

        pygame.draw.rect(self.lcd_display, COLOR_RED if post["liked"] else (220, 220, 230), btn_like, border_radius=6)
        heart_ic = pygame.transform.scale(self.pet.heart1_img, (12, 12))
        lk_txt = self.font_xs.render(f"{post['likes']}", False, (255, 255, 255) if post["liked"] else (60, 60, 70))
        self.lcd_display.blit(heart_ic, (btn_like.x + 8, btn_like.centery - 6))
        self.lcd_display.blit(lk_txt, (btn_like.x + 24, btn_like.centery - lk_txt.get_height() // 2))

        pygame.draw.rect(self.lcd_display, COLOR_SURFACE, btn_next, border_radius=6)
        pygame.draw.rect(self.lcd_display, COLOR_BORDER, btn_next, 2, border_radius=6)
        nx_txt = self.font_xs.render("TIẾP >", False, COLOR_TEXT_ORANGE)
        self.lcd_display.blit(nx_txt, (btn_next.centerx - nx_txt.get_width() // 2, btn_next.centery - nx_txt.get_height() // 2))

        pygame.draw.rect(self.lcd_display, COLOR_PURPLE_BACK, btn_back, border_radius=6)
        bk_txt = self.font_xs.render("ĐÓNG", False, (255, 255, 255))
        self.lcd_display.blit(bk_txt, (btn_back.centerx - bk_txt.get_width() // 2, btn_back.centery - bk_txt.get_height() // 2))

        self.clickable_lcd_areas.append((btn_like, self.press_button_b))
        self.clickable_lcd_areas.append((btn_next, self.press_button_a))
        self.clickable_lcd_areas.append((btn_back, self.press_button_c))

    def _draw_ui_guess_game(self):
        self.lcd_display.blit(self.striped_bg_a, (0, 0))
        card = pygame.Rect(10, 10, LCD_DISPLAY - 20, 128)
        pygame.draw.rect(self.lcd_display, COLOR_SURFACE, card, border_radius=10)
        pygame.draw.rect(self.lcd_display, COLOR_BORDER, card, 2, border_radius=10)

        t1 = self.font_xs.render(f"LƯỢT CÒN: {self.mg_timer}  (${self.mg_score})", False, COLOR_PURPLE_BACK)
        self.lcd_display.blit(t1, (card.centerx - t1.get_width() // 2, card.y + 8))

        num_surf = self.font_lg.render(str(self.mg_secret_num), False, COLOR_TEXT_ORANGE)
        self.lcd_display.blit(num_surf, (card.centerx - num_surf.get_width() // 2, card.y + 38))

        msg_surf = self.font_xs.render(self.mg_guess_msg, False, COLOR_TEXT_ORANGE)
        self.lcd_display.blit(msg_surf, (card.centerx - msg_surf.get_width() // 2, card.y + 88))

        btn_low = pygame.Rect(10, LCD_DISPLAY - 36, 82, 28)
        btn_high = pygame.Rect(100, LCD_DISPLAY - 36, 82, 28)
        for idx, (r_b, lbl) in enumerate([(btn_low, "NHỎ HƠN <"), (btn_high, "LỚN HƠN >")]):
            pygame.draw.rect(self.lcd_display, COLOR_SURFACE_ACTIVE if self.cursor_idx == idx else COLOR_SURFACE, r_b, border_radius=7)
            pygame.draw.rect(self.lcd_display, COLOR_BORDER, r_b, 2, border_radius=7)
            ls = self.font_xs.render(lbl, False, COLOR_TEXT_ORANGE)
            self.lcd_display.blit(ls, (r_b.centerx - ls.get_width() // 2, r_b.centery - ls.get_height() // 2))
            self.clickable_lcd_areas.append((r_b, lambda i=idx: self._check_guess_choice(i)))

    def _draw_ui_leaderboard(self):
        self.lcd_display.blit(self.striped_bg_b, (0, 0))
        card = pygame.Rect(6, 6, LCD_DISPLAY - 12, LCD_DISPLAY - 40)
        pygame.draw.rect(self.lcd_display, COLOR_SURFACE, card, border_radius=8)
        pygame.draw.rect(self.lcd_display, COLOR_BORDER, card, 2, border_radius=8)

        title = self.font_xs.render("BẢNG XẾP HẠNG HUBCHI", False, COLOR_PURPLE_BACK)
        self.lcd_display.blit(title, (card.centerx - title.get_width() // 2, card.y + 8))

        y_pos = card.y + 28
        for i, row in enumerate(self.leaderboard_rows[:5]):
            line = f"#{i+1} {row['pet_name'][:7]} CẤP {row['level']} ${row['score']}"
            surf = self.font_xs.render(line, False, COLOR_TEXT_ORANGE)
            self.lcd_display.blit(surf, (card.x + 8, y_pos))
            y_pos += 21

        self._draw_bottom_back_btn()

    def _draw_bottom_back_btn(self):
        btn_back = pygame.Rect(8, LCD_DISPLAY - 30, LCD_DISPLAY - 16, 24)
        pygame.draw.rect(self.lcd_display, COLOR_PURPLE_BACK, btn_back, border_radius=7)
        b_txt = self.font_xs.render("QUAY LẠI", False, (255, 255, 255))
        self.lcd_display.blit(b_txt, (btn_back.centerx - b_txt.get_width() // 2, btn_back.centery - b_txt.get_height() // 2))
        self._draw_pointer(btn_back.x + 4, btn_back.centery)
        self.clickable_lcd_areas.append((btn_back, self.press_button_c))

    # =========================================================================
    # MÀN HÌNH ĐĂNG NHẬP & ĐĂNG KÝ DỰA TRÊN ĐỒ HỌA PIXEL TAMAWEB
    # =========================================================================
    def _switch_auth_mode(self, mode: str):
        if self.auth_in_progress:
            return
        self.sound.play("click")
        self.auth_mode = mode
        self.auth_focus = 0
        self.auth_msg = ""

    def _submit_auth(self):
        if self.auth_in_progress:
            return
        uname = self.auth_username.strip().lower()
        pwd = self.auth_password.strip()
        if len(uname) < 3:
            self.sound.play("refuse")
            self.auth_msg = "TÀI KHOẢN PHẢI TỪ 3 KÝ TỰ TRỞ LÊN!"
            self.auth_msg_color = COLOR_RED
            return
        if len(pwd) < 3:
            self.sound.play("refuse")
            self.auth_msg = "MẬT KHẨU PHẢI TỪ 3 KÝ TỰ TRỞ LÊN!"
            self.auth_msg_color = COLOR_RED
            return

        if self.auth_mode == "register":
            if pwd != self.auth_confirm.strip():
                self.sound.play("refuse")
                self.auth_msg = "MẬT KHẨU NHẬP LẠI KHÔNG KHỚP!"
                self.auth_msg_color = COLOR_RED
                return

        self.sound.play("click")
        self.auth_in_progress = True
        self.auth_in_progress_time = 0.0
        self.auth_msg = ""
        self.auth_pending_mode = self.auth_mode
        self.auth_pending_user = uname
        self.auth_pending_pwd = pwd
        self.backend.start_auth_request(self.auth_mode, uname, pwd)
        if not IS_WEB:
            res = self.backend.check_auth_response()
            if res is not None:
                self._on_auth_complete(res)

    def _on_auth_complete(self, res: dict):
        try:
            self.auth_in_progress = False
            ok = res.get("ok", False)
            status = res.get("status", 0)
            data = res.get("data") or {}

            if ok:
                user = data.get("user") or {}
                self.backend.user_id = user.get("username", self.auth_pending_user)
                self.backend.role = "admin" if self.backend.user_id == "admin" else user.get("role", "user")
                self.backend.db_engine = user.get("database", "PostgreSQL")
                if data.get("dashboard"):
                    self.backend.set_cached_dashboard(data["dashboard"])

                # Lưu tài khoản vào cache localStorage
                self.backend.cache_user(self.backend.user_id, self.auth_pending_pwd)

                # Khởi tạo hoặc tải Pet
                self.pet = Pet(self.sound)
                pet_data = data.get("pet_data")
                if not pet_data:
                    pet_data = self.backend.load_pet()

                if pet_data:
                    self.pet.load_from_dict(pet_data)
                else:
                    self.pet.name = self.backend.user_id.upper()[:10]
                    self.backend.save_pet(self.pet.to_dict())

                self.sound.play("cheer_success")
                self.is_authenticated = True
                self.auth_msg = ""

                # Nếu là Quản trị viên (admin) -> Chuyển thẳng sang Trang Quản Lý Tài Khoản
                if self.backend.user_id == "admin" and self.backend.role == "admin":
                    self._enter_admin_dashboard()
                    return

                self.is_admin_mode = False
                if self.pet.stage == 0:
                    self.menu_state = None
                    self.show_toast("QUẢ TRỨNG SẮP NỞ RỒI!")
                else:
                    self.menu_state = "welcome_back"
                    self.show_toast(f"XIN CHÀO {self.backend.user_id.upper()}!")
            else:
                raw_err = data.get("detail") or data.get("message") or ""
                if isinstance(raw_err, list):
                    try:
                        err_str = str(raw_err[0].get("msg", raw_err[0]))
                    except Exception:
                        err_str = str(raw_err)
                else:
                    err_str = str(raw_err)

                if status == 0:
                    if self.auth_pending_mode == "login" and self.auth_pending_user == "admin" and self.auth_pending_pwd == "admin123":
                        self.backend.user_id = "admin"
                        self.backend.role = "admin"
                        self.backend.cache_user("admin", "admin123")
                        self.sound.play("cheer_success")
                        self.is_authenticated = True
                        self._enter_admin_dashboard()
                        return
                    cached_pwd = self.backend.get_cached_user(self.auth_pending_user)
                    if self.auth_pending_mode == "login" and cached_pwd and cached_pwd == self.auth_pending_pwd:
                        self.backend.user_id = self.auth_pending_user
                        self.backend.role = "admin" if self.auth_pending_user == "admin" else "user"
                        self.pet = Pet(self.sound)
                        saved = self.backend.load_pet()
                        if saved:
                            self.pet.load_from_dict(saved)
                        else:
                            self.pet.name = self.auth_pending_user.upper()[:10]
                        self.sound.play("cheer_success")
                        self.is_authenticated = True
                        if self.backend.user_id == "admin":
                            self._enter_admin_dashboard()
                        else:
                            self.is_admin_mode = False
                            self.menu_state = "welcome_back"
                            self.show_toast(f"ĐĂNG NHẬP: {self.backend.user_id.upper()}!")
                        return
                    elif self.auth_pending_mode == "register" and not cached_pwd:
                        self.backend.user_id = self.auth_pending_user
                        self.backend.role = "user"
                        self.backend.cache_user(self.auth_pending_user, self.auth_pending_pwd)
                        self.pet = Pet(self.sound)
                        self.pet.name = self.auth_pending_user.upper()[:10]
                        self.backend.save_pet(self.pet.to_dict())
                        self.sound.play("cheer_success")
                        self.is_authenticated = True
                        self.is_admin_mode = False
                        self.menu_state = "welcome_back"
                        return
                    err_str = "KHÔNG THỂ KẾT NỐI MÁY CHỦ!"

                if not err_str:
                    err_str = "TÀI KHOẢN ĐÃ TỒN TẠI!" if self.auth_pending_mode == "register" else "SAI TÀI KHOẢN / MẬT KHẨU!"

                self.sound.play("refuse")
                self.auth_msg = err_str.upper()[:42]
                self.auth_msg_color = COLOR_RED
        except Exception as e:
            print("_on_auth_complete error:", e)
            self.auth_in_progress = False
            self.sound.play("refuse")
            self.auth_msg = "LỖI XỬ LÝ ĐĂNG NHẬP!"
            self.auth_msg_color = COLOR_RED

    def _logout_account(self):
        self.sound.play("click")
        if not self.is_admin_mode:
            self.backend.save_pet(self.pet.to_dict())
        self.backend.logout()
        self.close_all_menus()
        self.is_authenticated = False
        self.is_admin_mode = False
        self.admin_modal = None
        self.auth_password = ""
        self.auth_confirm = ""
        self.auth_focus = 0
        self.auth_msg = ""
        self.auth_in_progress = False

    # =========================================================================
    # TRANG QUẢN TRỊ VIÊN - QUẢN LÝ TÀI KHOẢN (DỰA TRÊN ĐỒ HOẠ PIXEL TAMAWEB)
    # =========================================================================
    def _enter_admin_dashboard(self):
        if self.backend.user_id != "admin" or self.backend.role != "admin":
            self.is_admin_mode = False
            return
        self.sound.play("confirm")
        self.is_admin_mode = True
        self.admin_modal = None
        self.admin_search_focused = False
        self._refresh_admin_dashboard()
        self._set_admin_notice("CHÀO MỪNG QUẢN TRỊ VIÊN! HỆ THỐNG ĐÃ ĐỒNG BỘ.", COLOR_GREEN)

    def _switch_admin_to_game(self):
        self.sound.play("confirm")
        self.is_admin_mode = False
        self.admin_modal = None
        self.menu_state = None

    def _set_admin_notice(self, msg: str, color: tuple = COLOR_GREEN):
        self.admin_notice_msg = msg.upper()
        self.admin_notice_color = color
        self.admin_notice_timer = 3.5

    def _refresh_admin_dashboard(self, keep_selection: bool = True):
        data = self.backend.get_admin_dashboard()
        self.admin_dashboard = data or {}
        self.admin_stats = self.admin_dashboard.get("stats") or {
            "total_accounts": 0,
            "active_accounts": 0,
            "new_today_accounts": 0,
            "locked_accounts": 0,
            "online_players": 0,
            "inactive_accounts": 0,
        }
        self.admin_accounts = self.admin_dashboard.get("accounts") or []
        if self.admin_accounts:
            usernames = [a["username"] for a in self.admin_accounts]
            if not keep_selection or self.admin_selected_username not in usernames:
                # Ưu tiên chọn tài khoản người chơi đầu tiên hoặc tài khoản đầu danh sách
                non_admins = [a["username"] for a in self.admin_accounts if a["username"] != "admin"]
                self.admin_selected_username = non_admins[0] if non_admins else usernames[0]

    def _get_filtered_admin_accounts(self) -> list[dict]:
        q = self.admin_search_query.strip().lower()
        result = []
        for a in self.admin_accounts:
            st = a.get("status", "active")
            if self.admin_filter == "active" and st != "active":
                continue
            elif self.admin_filter == "today" and not a.get("is_registered_today"):
                continue
            elif self.admin_filter == "locked" and st != "locked":
                continue
            elif self.admin_filter == "online" and not a.get("is_online"):
                continue
            elif self.admin_filter == "inactive" and st != "inactive":
                continue

            if q:
                hay = f"{a.get('id', '')} {a.get('player_code', '')} {a.get('username', '')} {a.get('pet_name', '')}".lower()
                if q not in hay:
                    continue
            result.append(a)
        return result

    def _get_selected_admin_account(self) -> dict | None:
        for a in self.admin_accounts:
            if a["username"] == self.admin_selected_username:
                return a
        filtered = self._get_filtered_admin_accounts()
        if filtered:
            self.admin_selected_username = filtered[0]["username"]
            return filtered[0]
        if self.admin_accounts:
            self.admin_selected_username = self.admin_accounts[0]["username"]
            return self.admin_accounts[0]
        return None

    def _get_admin_char_sprite(self, char_path: str, frame_num: int = 1, size: int = 32) -> pygame.Surface:
        path = char_path or "resources/img/character/chara_1b.png"
        key = f"{path}::{frame_num}::{size}"
        if key in self.admin_sprite_cache:
            return self.admin_sprite_cache[key]
        try:
            raw = load_image(path)
            cell = max(16, raw.get_width() // 4)
            sheet = SpriteSheet(path, cell, 4, 4)
            surf = pygame.transform.scale(sheet.get_frame(frame_num), (size, size))
        except Exception:
            surf = pygame.transform.scale(self.auth_mascots[0].get_frame(1), (size, size))
        self.admin_sprite_cache[key] = surf
        return surf

    def _draw_clipped_text(
        self,
        surf: pygame.Surface,
        font,
        text: str,
        color: tuple,
        x: int,
        y: int,
        max_w: int,
        align: str = "left",
    ):
        s = str(text)
        if font.size(s)[0] > max_w and max_w > 20:
            while len(s) > 1 and font.size(s + "..")[0] > max_w:
                s = s[:-1]
            s = s + ".."
        t_surf = font.render(s, False, color)
        if align == "center":
            dx = x - t_surf.get_width() // 2
        elif align == "right":
            dx = x - t_surf.get_width()
        else:
            dx = x
        surf.blit(t_surf, (dx, y))

    def _draw_3d_button(
        self,
        rect: pygame.Rect,
        label: str,
        bg_col: tuple,
        fg_col: tuple = (255, 255, 255),
        border_col: tuple = COLOR_BORDER,
        shadow_col: tuple = (140, 80, 30),
        font=None,
        radius: int = 8,
    ):
        use_font = font or self.font_xs
        pygame.draw.rect(self.screen, shadow_col, rect.move(0, 3), border_radius=radius)
        pygame.draw.rect(self.screen, bg_col, rect, border_radius=radius)
        pygame.draw.rect(self.screen, border_col, rect, 2, border_radius=radius)
        self._draw_clipped_text(
            self.screen,
            use_font,
            label,
            fg_col,
            rect.centerx,
            rect.centery - use_font.get_height() // 2,
            rect.width - 8,
            align="center",
        )

    def _set_admin_filter(self, flt: str):
        self.sound.play("click")
        self.admin_filter = flt
        self.admin_page = 0
        if flt == "locked" and self.admin_detail_tab != "locked_list":
            filtered = self._get_filtered_admin_accounts()
            if filtered:
                self.admin_selected_username = filtered[0]["username"]

    def _select_admin_account(self, username: str):
        self.sound.play("click")
        self.admin_selected_username = username
        self.admin_search_focused = False
        if self.admin_detail_tab == "locked_list":
            self.admin_detail_tab = "all_4"

    def _set_admin_detail_tab(self, tab_id: str):
        self.sound.play("click")
        self.admin_detail_tab = tab_id
        self.admin_search_focused = False

    def _open_admin_add_modal(self):
        self.sound.play("click")
        self.admin_search_focused = False
        self.admin_modal = "add"
        self.admin_modal_focus = 0
        self.admin_form = {
            "username": "",
            "password": "123456",
            "status": "active",
            "level": "1",
            "total_xp": "100",
            "gold": "500",
            "unlocked_count": "2",
            "streak_days": "1",
            "last_device": "Web Browser (Tamaweb WASM)",
            "lock_reason": "Gian lận Coin & XP (Cheat/Hack)",
            "lock_duration_key": "24h",
        }

    def _open_admin_edit_modal(self):
        acc = self._get_selected_admin_account()
        if not acc:
            return
        self.sound.play("click")
        self.admin_search_focused = False
        self.admin_modal = "edit"
        self.admin_modal_focus = 0
        self.admin_form = {
            "username": acc["username"],
            "password": str(acc.get("password") or "123456"),
            "status": str(acc.get("status") or "active"),
            "level": str(acc.get("level") or 1),
            "total_xp": str(acc.get("total_xp") or 0),
            "gold": str(acc.get("gold") or 300),
            "unlocked_count": str(acc.get("unlocked_count") or 1),
            "streak_days": str(acc.get("streak_days") or 1),
            "last_device": str(acc.get("last_device") or "Web Browser (Tamaweb WASM)"),
            "lock_reason": str(acc.get("lock_reason") or "Gian lận Coin & XP (Cheat/Hack)"),
            "lock_duration_key": "24h",
        }

    def _open_admin_lock_modal(self, target_username: str = None):
        if target_username:
            self.admin_selected_username = target_username
        acc = self._get_selected_admin_account()
        if not acc:
            return
        if acc["username"] == "admin":
            self.sound.play("refuse")
            self._set_admin_notice("KHÔNG THỂ KHOÁ TÀI KHOẢN QUẢN TRỊ VIÊN GỐC!", COLOR_RED)
            return
        self.sound.play("click")
        self.admin_search_focused = False
        self.admin_modal = "lock"
        self.admin_modal_focus = 0
        self.admin_form["lock_reason"] = acc.get("lock_reason") or "Gian lận Coin & XP (Cheat/Hack)"
        self.admin_form["lock_duration_key"] = "24h"

    def _open_admin_delete_modal(self):
        acc = self._get_selected_admin_account()
        if not acc:
            return
        if acc["username"] == "admin":
            self.sound.play("refuse")
            self._set_admin_notice("KHÔNG THỂ XOÁ TÀI KHOẢN QUẢN TRỊ VIÊN GỐC!", COLOR_RED)
            return
        self.sound.play("click")
        self.admin_search_focused = False
        self.admin_modal = "delete"

    def _close_admin_modal(self):
        self.sound.play("cancel")
        self.admin_modal = None

    def _submit_admin_add_or_edit(self):
        try:
            lvl = max(1, int(self.admin_form.get("level") or 1))
        except Exception:
            lvl = 1
        try:
            txp = max(0, int(self.admin_form.get("total_xp") or 0))
        except Exception:
            txp = 0
        try:
            gld = max(0, int(self.admin_form.get("gold") or 0))
        except Exception:
            gld = 300
        try:
            uc = max(1, int(self.admin_form.get("unlocked_count") or 1))
        except Exception:
            uc = 1
        try:
            strk = max(1, int(self.admin_form.get("streak_days") or 1))
        except Exception:
            strk = 1

        payload = {
            "username": self.admin_form.get("username", "").strip().lower(),
            "password": self.admin_form.get("password", "").strip() or "123456",
            "status": self.admin_form.get("status", "active"),
            "level": lvl,
            "total_xp": txp,
            "gold": gld,
            "unlocked_count": uc,
            "streak_days": strk,
            "last_device": self.admin_form.get("last_device", "Web Browser (Tamaweb WASM)"),
        }

        if self.admin_modal == "add":
            ok, msg, _ = self.backend.admin_create_account(payload)
            if not ok:
                self.sound.play("refuse")
                self._set_admin_notice(msg, COLOR_RED)
                return
            self.sound.play("cheer_success")
            self.admin_selected_username = payload["username"]
            self.admin_modal = None
            self._refresh_admin_dashboard(keep_selection=True)
            self._set_admin_notice(msg, COLOR_GREEN)
        elif self.admin_modal == "edit":
            target = self.admin_selected_username
            ok, msg, _ = self.backend.admin_update_account(target, payload)
            if not ok:
                self.sound.play("refuse")
                self._set_admin_notice(msg, COLOR_RED)
                return
            self.sound.play("cheer_success")
            self.admin_modal = None
            self._refresh_admin_dashboard(keep_selection=True)
            self._set_admin_notice(msg, COLOR_GREEN)

    def _submit_admin_lock(self):
        acc = self._get_selected_admin_account()
        if not acc:
            return
        reason = self.admin_form.get("lock_reason", "").strip() or "Vi phạm quy định trò chơi"
        dur_key = self.admin_form.get("lock_duration_key", "24h")
        ok, msg, _ = self.backend.admin_lock_account(acc["username"], reason, dur_key)
        if not ok:
            self.sound.play("refuse")
            self._set_admin_notice(msg, COLOR_RED)
            return
        self.sound.play("complete")
        self.admin_modal = None
        self._refresh_admin_dashboard(keep_selection=True)
        self._set_admin_notice(msg, COLOR_RED)

    def _exec_admin_unlock(self, target_username: str = None):
        uname = target_username or self.admin_selected_username
        if not uname:
            return
        ok, msg, _ = self.backend.admin_unlock_account(uname, "Quản trị viên mở khoá tài khoản")
        if not ok:
            self.sound.play("refuse")
            self._set_admin_notice(msg, COLOR_RED)
            return
        self.sound.play("cheer_success")
        self._refresh_admin_dashboard(keep_selection=True)
        self._set_admin_notice(msg, COLOR_GREEN)

    def _submit_admin_delete(self):
        acc = self._get_selected_admin_account()
        if not acc:
            return
        ok, msg, _ = self.backend.admin_delete_account(acc["username"])
        if not ok:
            self.sound.play("refuse")
            self._set_admin_notice(msg, COLOR_RED)
            return
        self.sound.play("complete")
        self.admin_modal = None
        self._refresh_admin_dashboard(keep_selection=False)
        self._set_admin_notice(msg, COLOR_TEXT_ORANGE)

    def _quick_adjust_game_stat(self, field: str, delta: int):
        acc = self._get_selected_admin_account()
        if not acc:
            return
        self.sound.play("click")
        new_val = max(1 if field in ("level", "unlocked_count", "streak_days") else 0, int(acc.get(field) or 0) + delta)
        ok, msg, _ = self.backend.admin_update_account(acc["username"], {field: new_val})
        if ok:
            self._refresh_admin_dashboard(keep_selection=True)
            self._set_admin_notice(f"ĐÃ CẬP NHẬT {field.upper()} = {new_val}!", COLOR_GREEN)

    def _draw_admin_screen(self):
        self.admin_click_areas.clear()
        self.admin_modal_click_areas.clear()

        # Bảo mật: Chỉ tài khoản admin mới có quyền truy cập trang quản trị
        if self.backend.user_id != "admin" or self.backend.role != "admin":
            self.is_admin_mode = False
            return

        # Khung nền lớn của Trang Quản Lý Tài Khoản (chuẩn đồ hoạ thẻ 3D Tamaweb)
        panel = pygame.Rect(36, 16, WIN_W - 72, WIN_H - 32)
        pygame.draw.rect(self.screen, (110, 65, 25, 90), panel.move(0, 7), border_radius=18)
        pygame.draw.rect(self.screen, COLOR_SURFACE_SHADOW, panel.move(0, 4), border_radius=18)
        pygame.draw.rect(self.screen, COLOR_SURFACE, panel, border_radius=18)
        pygame.draw.rect(self.screen, COLOR_BORDER, panel, 4, border_radius=18)

        # =====================================================================
        # 1. THANH HEADER QUẢN TRỊ VIÊN (LOGO TAMAWEB + MASCOT + CÔNG CỤ NHANH)
        # =====================================================================
        hdr_rect = pygame.Rect(50, 26, WIN_W - 100, 52)
        self.screen.blit(self.striped_admin_hdr, hdr_rect.topleft)
        pygame.draw.rect(self.screen, COLOR_BORDER, hdr_rect, 2, border_radius=12)

        logo_adm = pygame.transform.smoothscale(self.logo_img, (108, 42))
        self.screen.blit(logo_adm, (hdr_rect.x + 10, hdr_rect.y + 5))

        frame_num = 1 if int(self.auth_anim_tick * 3.0) % 2 == 0 else 2
        mascot_adm = pygame.transform.scale(self.auth_mascots[0].get_frame(frame_num), (38, 38))
        self.screen.blit(mascot_adm, (hdr_rect.x + 124, hdr_rect.y + 7))

        title_s = self.font_md.render("TRANG QUẢN LÝ TÀI KHOẢN - ADMIN PANEL", False, COLOR_TEXT_ORANGE)
        self.screen.blit(title_s, (hdr_rect.x + 168, hdr_rect.y + 7))

        if self.admin_notice_msg:
            self._draw_clipped_text(self.screen, self.font_xs, f"• {self.admin_notice_msg}", self.admin_notice_color, hdr_rect.x + 168, hdr_rect.y + 30, 470)
        else:
            sub_txt = f"QUYỀN: ADMIN ({self.backend.user_id.upper()})  •  CƠ SỞ DỮ LIỆU: {self.admin_dashboard.get('database', 'PostgreSQL / SQLite')}"
            self._draw_clipped_text(self.screen, self.font_xs, sub_txt, COLOR_PURPLE_BACK, hdr_rect.x + 168, hdr_rect.y + 30, 470)

        # Thông báo thao tác (nếu có) hoặc các nút chức năng trên Header
        locked_cnt = self.admin_stats.get("locked_accounts", 0)
        btn_add_top = pygame.Rect(hdr_rect.right - 526, hdr_rect.y + 9, 128, 34)
        btn_locked_top = pygame.Rect(hdr_rect.right - 392, hdr_rect.y + 9, 138, 34)
        btn_refresh = pygame.Rect(hdr_rect.right - 248, hdr_rect.y + 9, 76, 34)
        btn_to_game = pygame.Rect(hdr_rect.right - 166, hdr_rect.y + 9, 76, 34)
        btn_logout = pygame.Rect(hdr_rect.right - 84, hdr_rect.y + 9, 76, 34)

        self._draw_3d_button(btn_add_top, "+ THÊM TÀI KHOẢN", COLOR_GREEN, (255, 255, 255), (35, 135, 25), (30, 110, 20))
        self.admin_click_areas.append((btn_add_top, self._open_admin_add_modal))

        lk_active = (self.admin_detail_tab == "locked_list" or self.admin_filter == "locked")
        self._draw_3d_button(
            btn_locked_top,
            f"DS BỊ KHOÁ ({locked_cnt})",
            COLOR_RED if lk_active else (255, 230, 234),
            (255, 255, 255) if lk_active else COLOR_RED,
            COLOR_RED,
            (150, 20, 45),
        )
        self.admin_click_areas.append((btn_locked_top, self._toggle_locked_accounts_view))

        self._draw_3d_button(btn_refresh, "LÀM MỚI", COLOR_SURFACE_ACTIVE, COLOR_TEXT_ORANGE)
        self.admin_click_areas.append((btn_refresh, self._manual_refresh_admin))

        self._draw_3d_button(btn_to_game, "VÀO GAME", COLOR_TEXT_ORANGE, (255, 255, 255), (190, 90, 10), (150, 65, 0))
        self.admin_click_areas.append((btn_to_game, self._switch_admin_to_game))

        self._draw_3d_button(btn_logout, "ĐĂNG XUẤT", COLOR_PURPLE_BACK, (255, 255, 255), (35, 0, 160), (25, 0, 120))
        self.admin_click_areas.append((btn_logout, self._logout_account))

        # =====================================================================
        # 2. HÀNG 6 THẺ CHỈ SỐ THỐNG KÊ TỔNG QUAN (CLICK ĐỂ LỌC DANH SÁCH)
        # =====================================================================
        stat_Specs = [
            ("all",      "TỔNG SỐ TÀI KHOẢN",      self.admin_stats.get("total_accounts", 0),     (255, 128, 0),  "TẤT CẢ TK"),
            ("active",   "TK ĐANG HOẠT ĐỘNG",      self.admin_stats.get("active_accounts", 0),    (62, 185, 45),  "HOẠT ĐỘNG"),
            ("today",    "ĐĂNG KÝ MỚI HÔM NAY",    self.admin_stats.get("new_today_accounts", 0), (35, 130, 225), "MỚI HÔM NAY"),
            ("locked",   "SỐ TÀI KHOẢN BỊ KHOÁ",   self.admin_stats.get("locked_accounts", 0),    (237, 37, 78),  "ĐANG KHOÁ"),
            ("online",   "NGƯỜI CHƠI ĐANG ONLINE", self.admin_stats.get("online_players", 0),     (18, 165, 130), "TRỰC TUYẾN"),
            ("inactive", "TK KHÔNG HOẠT ĐỘNG",     self.admin_stats.get("inactive_accounts", 0),  (135, 105, 80), "NGƯNG HĐ"),
        ]
        card_w = 189
        card_gap = 9
        stat_y = 85
        for idx, (flt_key, title_lbl, val_num, accent_col, badge_lbl) in enumerate(stat_Specs):
            sx = 50 + idx * (card_w + card_gap)
            s_rect = pygame.Rect(sx, stat_y, card_w, 68)
            is_sel = (self.admin_filter == flt_key)
            pygame.draw.rect(self.screen, COLOR_SURFACE_SHADOW, s_rect.move(0, 3), border_radius=11)
            pygame.draw.rect(self.screen, (255, 250, 242) if is_sel else (255, 255, 255), s_rect, border_radius=11)
            # Dải màu điểm nhấn trên đỉnh thẻ
            top_strip = pygame.Rect(s_rect.x + 2, s_rect.y + 2, s_rect.width - 4, 7)
            pygame.draw.rect(self.screen, accent_col, top_strip, border_radius=5)
            pygame.draw.rect(self.screen, accent_col if is_sel else COLOR_BORDER, s_rect, 3 if is_sel else 2, border_radius=11)

            # Số lượng lớn + Nhãn badge góc phải
            num_s = self.font_lg.render(str(val_num), False, accent_col)
            self.screen.blit(num_s, (s_rect.x + 12, s_rect.y + 13))

            pill_r = pygame.Rect(s_rect.right - 92, s_rect.y + 15, 84, 18)
            pygame.draw.rect(self.screen, accent_col, pill_r, border_radius=6)
            self._draw_clipped_text(self.screen, self.font_xs, badge_lbl, (255, 255, 255), pill_r.centerx, pill_r.y + 2, 80, align="center")

            self._draw_clipped_text(self.screen, self.font_xs, title_lbl, (75, 45, 20), s_rect.x + 10, s_rect.y + 46, s_rect.width - 16)
            self.admin_click_areas.append((s_rect, lambda f=flt_key: self._set_admin_filter(f)))

        # =====================================================================
        # 3. CỘT TRÁI: DANH SÁCH TÀI KHOẢN + TÌM KIẾM + BỘ LỌC (x=50, y=161)
        # =====================================================================
        left_box = pygame.Rect(50, 161, 456, 526)
        pygame.draw.rect(self.screen, COLOR_SURFACE_SHADOW, left_box.move(0, 3), border_radius=14)
        pygame.draw.rect(self.screen, (255, 252, 247), left_box, border_radius=14)
        pygame.draw.rect(self.screen, COLOR_BORDER, left_box, 3, border_radius=14)

        # Ô tìm kiếm tài khoản
        search_rect = pygame.Rect(left_box.x + 10, left_box.y + 10, 306, 30)
        pygame.draw.rect(self.screen, (255, 255, 255), search_rect, border_radius=8)
        pygame.draw.rect(self.screen, COLOR_PURPLE_BACK if self.admin_search_focused else COLOR_BORDER, search_rect, 2, border_radius=8)
        blink = "|" if (self.admin_search_focused and int(self.auth_anim_tick * 2.5) % 2 == 0) else ""
        if self.admin_search_query or self.admin_search_focused:
            q_disp = f"Tìm: {self.admin_search_query}{blink}"
            q_col = (35, 20, 10)
        else:
            q_disp = "Tìm kiếm ID, Username, Tên Pet..."
            q_col = (180, 160, 140)
        self._draw_clipped_text(self.screen, self.font_xs, q_disp, q_col, search_rect.x + 10, search_rect.y + 8, search_rect.width - 20)
        self.admin_click_areas.append((search_rect, self._focus_admin_search))

        btn_clr_q = pygame.Rect(search_rect.right + 5, search_rect.y, 32, 30)
        self._draw_3d_button(btn_clr_q, "X", COLOR_SURFACE_SHADOW, COLOR_TEXT_ORANGE)
        self.admin_click_areas.append((btn_clr_q, self._clear_admin_search))

        btn_new_l = pygame.Rect(btn_clr_q.right + 6, search_rect.y, 87, 30)
        self._draw_3d_button(btn_new_l, "+ THÊM MỚI", COLOR_GREEN, (255, 255, 255), (35, 135, 25), (30, 110, 20))
        self.admin_click_areas.append((btn_new_l, self._open_admin_add_modal))

        # Thanh nút lọc nhanh
        filter_tabs = [
            ("all", "TẤT CẢ"),
            ("active", "HOẠT ĐỘNG"),
            ("online", "ONLINE"),
            ("locked", "BỊ KHOÁ"),
            ("today", "HÔM NAY"),
            ("inactive", "K.HĐ"),
        ]
        fx = left_box.x + 10
        fy = left_box.y + 46
        for f_key, f_lbl in filter_tabs:
            fw = 70 if len(f_lbl) <= 7 else 82
            if f_key == "inactive":
                fw = 56
            f_rect = pygame.Rect(fx, fy, fw, 23)
            act = (self.admin_filter == f_key)
            pygame.draw.rect(self.screen, COLOR_TEXT_ORANGE if act else COLOR_SURFACE_SHADOW, f_rect, border_radius=6)
            pygame.draw.rect(self.screen, COLOR_BORDER, f_rect, 1, border_radius=6)
            self._draw_clipped_text(
                self.screen,
                self.font_xs,
                f_lbl,
                (255, 255, 255) if act else (95, 55, 20),
                f_rect.centerx,
                f_rect.y + 4,
                fw - 4,
                align="center",
            )
            self.admin_click_areas.append((f_rect, lambda k=f_key: self._set_admin_filter(k)))
            fx += fw + 4

        # Tiêu đề cột bảng danh sách
        tbl_hdr = pygame.Rect(left_box.x + 10, left_box.y + 74, left_box.width - 20, 22)
        pygame.draw.rect(self.screen, COLOR_SURFACE_ACTIVE, tbl_hdr, border_radius=6)
        self._draw_clipped_text(self.screen, self.font_xs, "ID / USERNAME", (90, 45, 10), tbl_hdr.x + 44, tbl_hdr.y + 4, 150)
        self._draw_clipped_text(self.screen, self.font_xs, "LV • COIN • CHUỖI", (90, 45, 10), tbl_hdr.x + 195, tbl_hdr.y + 4, 130)
        self._draw_clipped_text(self.screen, self.font_xs, "TRẠNG THÁI", (90, 45, 10), tbl_hdr.right - 84, tbl_hdr.y + 4, 80)

        # Các dòng tài khoản (7 dòng / trang)
        filtered_accs = self._get_filtered_admin_accounts()
        per_page = 7
        total_pages = max(1, (len(filtered_accs) + per_page - 1) // per_page)
        self.admin_page = max(0, min(self.admin_page, total_pages - 1))
        page_items = filtered_accs[self.admin_page * per_page : (self.admin_page + 1) * per_page]

        row_y = left_box.y + 100
        row_h = 50
        if not page_items:
            empty_s = self.font_sm.render("KHÔNG CÓ TÀI KHOẢN NÀO PHÙ HỢP!", False, COLOR_TEXT_ORANGE)
            self.screen.blit(empty_s, (left_box.centerx - empty_s.get_width() // 2, left_box.y + 220))
        else:
            for acc in page_items:
                is_cur = (acc["username"] == self.admin_selected_username)
                r_rect = pygame.Rect(left_box.x + 10, row_y, left_box.width - 20, row_h - 4)
                bg_r = (255, 232, 204) if is_cur else (255, 255, 255)
                bd_r = COLOR_PURPLE_BACK if is_cur else COLOR_BORDER
                pygame.draw.rect(self.screen, bg_r, r_rect, border_radius=9)
                pygame.draw.rect(self.screen, bd_r, r_rect, 3 if is_cur else 1, border_radius=9)

                # Avatar sprite nhân vật của tài khoản
                av_box = pygame.Rect(r_rect.x + 6, r_rect.y + 6, 34, 34)
                pygame.draw.rect(self.screen, COLOR_SURFACE, av_box, border_radius=7)
                pygame.draw.rect(self.screen, COLOR_BORDER, av_box, 1, border_radius=7)
                spr = self._get_admin_char_sprite(acc.get("character_file"), frame_num if is_cur else 1, 30)
                self.screen.blit(spr, (av_box.x + 2, av_box.y + 2))

                # ID + Username
                u_title = f"#{acc['id']} {acc['username'].upper()}"
                if acc.get("role") == "admin":
                    u_title += " [ADMIN]"
                self._draw_clipped_text(self.screen, self.font_xs, u_title, COLOR_PURPLE_BACK if is_cur else (45, 25, 10), r_rect.x + 46, r_rect.y + 6, 145)
                self._draw_clipped_text(self.screen, self.font_xs, f"Ngày: {acc.get('created_at_str', '')[:10]}", (130, 100, 75), r_rect.x + 46, r_rect.y + 25, 145)

                # Level, Coin, Streak
                self._draw_clipped_text(self.screen, self.font_xs, f"LV.{acc['level']}  •  ${acc['gold']:,}", COLOR_TEXT_ORANGE, r_rect.x + 195, r_rect.y + 6, 135)
                self._draw_clipped_text(self.screen, self.font_xs, f"XP:{acc['total_xp']} • {acc['streak_days']} ngày", (110, 85, 60), r_rect.x + 195, r_rect.y + 25, 135)

                # Badge trạng thái
                st = acc.get("status", "active")
                if st == "locked":
                    b_col, b_txt = COLOR_RED, "BỊ KHOÁ"
                elif st == "inactive":
                    b_col, b_txt = (140, 115, 95), "K.HOẠT ĐỘNG"
                elif acc.get("is_online"):
                    b_col, b_txt = (22, 168, 95), "● ONLINE"
                else:
                    b_col, b_txt = (85, 180, 60), "HOẠT ĐỘNG"

                st_pill = pygame.Rect(r_rect.right - 92, r_rect.y + 12, 84, 22)
                pygame.draw.rect(self.screen, b_col, st_pill, border_radius=7)
                self._draw_clipped_text(self.screen, self.font_xs, b_txt, (255, 255, 255), st_pill.centerx, st_pill.y + 4, 78, align="center")

                uname_val = acc["username"]
                self.admin_click_areas.append((r_rect, lambda u=uname_val: self._select_admin_account(u)))
                row_y += row_h

        # Thanh phân trang dưới đáy cột trái
        pag_y = left_box.bottom - 34
        btn_prev = pygame.Rect(left_box.x + 10, pag_y, 82, 26)
        btn_next = pygame.Rect(left_box.right - 92, pag_y, 82, 26)
        self._draw_3d_button(btn_prev, "< TRƯỚC", COLOR_SURFACE_ACTIVE, COLOR_TEXT_ORANGE)
        self._draw_3d_button(btn_next, "TIẾP >", COLOR_SURFACE_ACTIVE, COLOR_TEXT_ORANGE)
        self.admin_click_areas.append((btn_prev, lambda: self._change_admin_page(-1)))
        self.admin_click_areas.append((btn_next, lambda: self._change_admin_page(1)))

        pag_lbl = f"TRANG {self.admin_page + 1}/{total_pages} ({len(filtered_accs)} TK)"
        self._draw_clipped_text(self.screen, self.font_xs, pag_lbl, (95, 60, 30), left_box.centerx, pag_y + 6, 240, align="center")

        # =====================================================================
        # 4. CỘT PHẢI: CHI TIẾT TÀI KHOẢN (4 PHẦN) & THAO TÁC (x=514, y=161)
        # =====================================================================
        right_box = pygame.Rect(514, 161, 716, 526)
        pygame.draw.rect(self.screen, COLOR_SURFACE_SHADOW, right_box.move(0, 3), border_radius=14)
        pygame.draw.rect(self.screen, (255, 252, 247), right_box, border_radius=14)
        pygame.draw.rect(self.screen, COLOR_BORDER, right_box, 3, border_radius=14)

        sel_acc = self._get_selected_admin_account()
        if not sel_acc:
            return

        # 4A. Banner Hồ sơ Người chơi đang chọn + Cụm nút Thêm / Sửa / Khoá / Mở khoá / Xoá
        prof_bar = pygame.Rect(right_box.x + 10, right_box.y + 10, right_box.width - 20, 74)
        pygame.draw.rect(self.screen, COLOR_SURFACE, prof_bar, border_radius=11)
        pygame.draw.rect(self.screen, COLOR_BORDER, prof_bar, 2, border_radius=11)

        # Khung cảnh game thu nhỏ + Nhân vật nhún nhảy
        mini_scene = pygame.Rect(prof_bar.x + 8, prof_bar.y + 7, 60, 60)
        mini_surf = pygame.Surface((60, 60))
        mini_surf.blit(pygame.transform.scale(self.get_current_sky(), (60, 60)), (0, 0))
        mini_surf.blit(pygame.transform.scale(self.scene_bgs["park"], (60, 68)), (0, -8))
        p_spr = self._get_admin_char_sprite(sel_acc.get("character_file"), frame_num, 44)
        mini_surf.blit(p_spr, (8, 12))
        self.screen.blit(mini_surf, mini_scene.topleft)
        pygame.draw.rect(self.screen, COLOR_BORDER, mini_scene, 2, border_radius=8)

        # Thông tin tóm tắt trên Banner
        head_line = f"{sel_acc['player_code']} (ID #{sel_acc['id']})  •  @{sel_acc['username'].upper()}"
        self._draw_clipped_text(self.screen, self.font_md, head_line, COLOR_PURPLE_BACK, prof_bar.x + 78, prof_bar.y + 8, 330)

        st = sel_acc.get("status", "active")
        st_label = sel_acc.get("status_vn", "Đang hoạt động").upper()
        on_label = "• ĐANG ONLINE" if sel_acc.get("is_online") else "• OFFLINE"
        st_col = COLOR_RED if st == "locked" else ((130, 105, 80) if st == "inactive" else (30, 155, 55))
        self._draw_clipped_text(
            self.screen,
            self.font_xs,
            f"TRẠNG THÁI: {st_label}   |   {on_label}   |   VAI TRÒ: {sel_acc.get('role', 'user').upper()}",
            st_col,
            prof_bar.x + 78,
            prof_bar.y + 32,
            365,
        )
        sub_info = f"Tạo: {sel_acc.get('created_at_str')}  •  Thiết bị: {sel_acc.get('last_device')}"
        self._draw_clipped_text(self.screen, self.font_xs, sub_info, (115, 80, 50), prof_bar.x + 78, prof_bar.y + 51, 365)

        # Cụm nút CRUD & Khoá / Mở khoá ở góc phải Banner
        act_x = prof_bar.right - 242
        btn_edit_acc = pygame.Rect(act_x, prof_bar.y + 8, 114, 26)
        btn_del_acc = pygame.Rect(act_x + 120, prof_bar.y + 8, 114, 26)
        btn_lock_toggle = pygame.Rect(act_x, prof_bar.y + 40, 234, 26)

        self._draw_3d_button(btn_edit_acc, "SỬA TÀI KHOẢN", COLOR_TEXT_ORANGE, (255, 255, 255), (185, 85, 0), (145, 65, 0))
        self.admin_click_areas.append((btn_edit_acc, self._open_admin_edit_modal))

        self._draw_3d_button(btn_del_acc, "XOÁ TÀI KHOẢN", (195, 45, 65), (255, 255, 255), (140, 20, 35), (110, 15, 30))
        self.admin_click_areas.append((btn_del_acc, self._open_admin_delete_modal))

        if st == "locked":
            self._draw_3d_button(btn_lock_toggle, "MỞ KHOÁ TÀI KHOẢN NGAY", (22, 168, 95), (255, 255, 255), (15, 120, 65), (10, 95, 50))
            self.admin_click_areas.append((btn_lock_toggle, lambda u=sel_acc["username"]: self._exec_admin_unlock(u)))
        else:
            self._draw_3d_button(btn_lock_toggle, "KHOÁ TÀI KHOẢN (LÝ DO & HẠN)", COLOR_RED, (255, 255, 255), (165, 20, 45), (130, 10, 35))
            self.admin_click_areas.append((btn_lock_toggle, lambda u=sel_acc["username"]: self._open_admin_lock_modal(u)))

        # 4B. Thanh chuyển đổi 4 Phần thông tin
        tab_bar_y = right_box.y + 90

        detail_tabs = [
            ("all_4",       "TỔNG HỢP 4 PHẦN"),
            ("part1",       "1. TT CÁ NHÂN"),
            ("part2",       "2. TT TRÒ CHƠI"),
            ("part3",       "3. HOẠT ĐỘNG"),
            ("part4",       "4. LS XỬ LÝ"),
            ("locked_list", f"DS BỊ KHOÁ ({locked_cnt})"),
        ]
        tx = right_box.x + 10
        tw = (right_box.width - 20 - 5 * 5) // 6
        for t_id, t_lbl in detail_tabs:
            t_rect = pygame.Rect(tx, tab_bar_y, tw, 26)
            is_t = (self.admin_detail_tab == t_id)
            t_bg = COLOR_PURPLE_BACK if is_t else (COLOR_RED if t_id == "locked_list" and locked_cnt > 0 else COLOR_SURFACE_SHADOW)
            t_fg = (255, 255, 255) if (is_t or (t_id == "locked_list" and locked_cnt > 0)) else (85, 45, 15)
            pygame.draw.rect(self.screen, t_bg, t_rect, border_radius=7)
            pygame.draw.rect(self.screen, COLOR_BORDER, t_rect, 2 if is_t else 1, border_radius=7)
            self._draw_clipped_text(self.screen, self.font_xs, t_lbl, t_fg, t_rect.centerx, t_rect.y + 5, tw - 6, align="center")
            self.admin_click_areas.append((t_rect, lambda k=t_id: self._set_admin_detail_tab(k)))
            tx += tw + 5

        content_y = tab_bar_y + 32
        content_rect = pygame.Rect(right_box.x + 10, content_y, right_box.width - 20, right_box.bottom - content_y - 10)

        if self.admin_detail_tab == "all_4":
            self._draw_admin_four_sections_grid(content_rect, sel_acc)
        elif self.admin_detail_tab == "part1":
            self._draw_admin_part1_expanded(content_rect, sel_acc)
        elif self.admin_detail_tab == "part2":
            self._draw_admin_part2_expanded(content_rect, sel_acc)
        elif self.admin_detail_tab == "part3":
            self._draw_admin_part3_expanded(content_rect, sel_acc)
        elif self.admin_detail_tab == "part4":
            self._draw_admin_part4_expanded(content_rect, sel_acc)
        elif self.admin_detail_tab == "locked_list":
            self._draw_admin_locked_accounts_table(content_rect)

        # =====================================================================
        # 5. MODAL HỘP THOẠI (THÊM / SỬA / KHOÁ / XOÁ TÀI KHOẢN)
        # =====================================================================
        if self.admin_modal:
            self._draw_admin_modal_overlay()

    def _draw_section_card_frame(self, rect: pygame.Rect, title: str, badge_txt: str = "", header_col: tuple = COLOR_STRIPE_A1, tab_target: str = None):
        pygame.draw.rect(self.screen, COLOR_SURFACE_SHADOW, rect.move(0, 2), border_radius=11)
        pygame.draw.rect(self.screen, (255, 255, 255), rect, border_radius=11)
        hdr = pygame.Rect(rect.x + 2, rect.y + 2, rect.width - 4, 26)
        pygame.draw.rect(self.screen, header_col, hdr, border_radius=9)
        pygame.draw.rect(self.screen, COLOR_BORDER, rect, 2, border_radius=11)
        pygame.draw.line(self.screen, COLOR_BORDER, (rect.x, hdr.bottom), (rect.right, hdr.bottom), 2)
        self._draw_clipped_text(self.screen, self.font_xs, title, COLOR_PURPLE_BACK, hdr.x + 10, hdr.y + 5, hdr.width - 95)
        if badge_txt:
            b_rect = pygame.Rect(hdr.right - 84, hdr.y + 3, 78, 20)
            pygame.draw.rect(self.screen, COLOR_SURFACE, b_rect, border_radius=6)
            pygame.draw.rect(self.screen, COLOR_BORDER, b_rect, 1, border_radius=6)
            self._draw_clipped_text(self.screen, self.font_xs, badge_txt, COLOR_TEXT_ORANGE, b_rect.centerx, b_rect.y + 2, 72, align="center")
            if tab_target:
                self.admin_click_areas.append((b_rect, lambda t=tab_target: self._set_admin_detail_tab(t)))

    def _draw_kv_row(self, x: int, y: int, w: int, label: str, val: str, val_col: tuple = (40, 25, 10)):
        pygame.draw.rect(self.screen, (255, 248, 238), (x, y, w, 24), border_radius=6)
        pygame.draw.rect(self.screen, (245, 222, 195), (x, y, w, 24), 1, border_radius=6)
        self._draw_clipped_text(self.screen, self.font_xs, label, (115, 75, 40), x + 8, y + 4, int(w * 0.46))
        self._draw_clipped_text(self.screen, self.font_xs, val, val_col, x + w - 8, y + 4, int(w * 0.52), align="right")

    def _draw_admin_four_sections_grid(self, area: pygame.Rect, acc: dict):
        """Hiển thị đồng thời cả 4 Phần thông tin tài khoản theo bố cục lưới 2x2 chuẩn đồ hoạ game"""
        gap = 10
        cw = (area.width - gap) // 2
        ch = (area.height - gap) // 2

        c1 = pygame.Rect(area.x, area.y, cw, ch)
        c2 = pygame.Rect(area.x + cw + gap, area.y, cw, ch)
        c3 = pygame.Rect(area.x, area.y + ch + gap, cw, ch)
        c4 = pygame.Rect(area.x + cw + gap, area.y + ch + gap, cw, ch)

        # ---------------------------------------------------------------------
        # PHẦN 1. THÔNG TIN CÁ NHÂN
        # ---------------------------------------------------------------------
        self._draw_section_card_frame(c1, "PHẦN 1. THÔNG TIN CÁ NHÂN", "CHI TIẾT >", COLOR_STRIPE_A1, "part1")
        st = acc.get("status", "active")
        st_col = COLOR_RED if st == "locked" else ((130, 105, 80) if st == "inactive" else (25, 155, 55))
        st_full = f"{acc.get('status_vn', 'Đang hoạt động')} ({'Online' if acc.get('is_online') else 'Offline'})"

        y1 = c1.y + 34
        self._draw_kv_row(c1.x + 8, y1,      cw - 16, "1. ID người chơi:", f"#{acc['id']} ({acc['player_code']})", COLOR_PURPLE_BACK)
        self._draw_kv_row(c1.x + 8, y1 + 28, cw - 16, "2. Username:", f"{acc['username']} ({acc.get('role', 'user').upper()})", COLOR_TEXT_ORANGE)
        self._draw_kv_row(c1.x + 8, y1 + 56, cw - 16, "3. Ngày tạo TK:", acc.get("created_at_str", "--"))
        self._draw_kv_row(c1.x + 8, y1 + 84, cw - 16, "4. Trạng thái TK:", st_full, st_col)

        pw_raw = str(acc.get("password") or "******")
        pw_disp = pw_raw if self.admin_show_user_pw else ("*" * max(6, len(pw_raw)))
        self._draw_kv_row(c1.x + 8, y1 + 112, cw - 82, "Mật khẩu:", pw_disp, (90, 60, 35))
        btn_pw_t = pygame.Rect(c1.right - 70, y1 + 112, 62, 24)
        self._draw_3d_button(btn_pw_t, "ẨN" if self.admin_show_user_pw else "HIỆN", COLOR_SURFACE_ACTIVE, COLOR_TEXT_ORANGE, radius=6)
        self.admin_click_areas.append((btn_pw_t, self._toggle_admin_user_pw))

        # ---------------------------------------------------------------------
        # PHẦN 2. THÔNG TIN TRÒ CHƠI
        # ---------------------------------------------------------------------
        self._draw_section_card_frame(c2, "PHẦN 2. THÔNG TIN TRÒ CHƠI", "CHI TIẾT >", COLOR_STRIPE_A2, "part2")
        y2 = c2.y + 34
        self._draw_kv_row(c2.x + 8, y2,       cw - 16, "1. Level hiện tại:", f"Level {acc['level']} ({acc.get('pet_name', 'TAMA')})", COLOR_TEXT_ORANGE)
        self._draw_kv_row(c2.x + 8, y2 + 28,  cw - 16, "2. Tổng XP:", f"{acc['total_xp']:,} XP", COLOR_PURPLE_BACK)
        self._draw_kv_row(c2.x + 8, y2 + 56,  cw - 16, "3. Tổng Coin:", f"{acc['gold']:,} Coin ($)", (210, 125, 0))
        self._draw_kv_row(c2.x + 8, y2 + 84,  cw - 16, "4. Nhân vật mở khoá:", f"{acc['unlocked_count']} Nhân vật", (25, 150, 65))
        self._draw_kv_row(c2.x + 8, y2 + 112, cw - 16, "5. Chuỗi ngày duy trì:", f"{acc['streak_days']} Ngày liên tiếp", COLOR_RED)

        # ---------------------------------------------------------------------
        # PHẦN 3. HOẠT ĐỘNG TÀI KHOẢN
        # ---------------------------------------------------------------------
        self._draw_section_card_frame(c3, "PHẦN 3. HOẠT ĐỘNG TÀI KHOẢN", "NHẬT KÝ >", COLOR_STRIPE_B2, "part3")
        y3 = c3.y + 34
        self._draw_kv_row(c3.x + 8, y3,      cw - 16, "1. Đăng nhập cuối:", acc.get("last_login_str", "--"))
        self._draw_kv_row(c3.x + 8, y3 + 27, cw - 16, "2. Tổng số lần ĐN:", f"{acc.get('login_count', 1)} Lần", COLOR_PURPLE_BACK)
        self._draw_kv_row(c3.x + 8, y3 + 54, cw - 16, "4. Thiết bị ĐN:", acc.get("last_device", "Web Browser"))

        # 3. Lịch sử hoạt động (tóm tắt các sự kiện gần nhất)
        act_box = pygame.Rect(c3.x + 8, y3 + 81, cw - 16, c3.bottom - (y3 + 87))
        pygame.draw.rect(self.screen, (255, 248, 238), act_box, border_radius=6)
        pygame.draw.rect(self.screen, (245, 222, 195), act_box, 1, border_radius=6)
        self._draw_clipped_text(self.screen, self.font_xs, "3. Lịch sử hoạt động gần đây:", COLOR_TEXT_ORANGE, act_box.x + 6, act_box.y + 3, act_box.width - 12)
        acts = acc.get("activity_history") or []
        ay = act_box.y + 20
        for act_item in acts[:2]:
            line = f"• [{act_item.get('time_str', '')[:16]}] {act_item.get('description', '')}"
            self._draw_clipped_text(self.screen, self.font_xs, line, (65, 45, 25), act_box.x + 6, ay, act_box.width - 12)
            ay += 17

        # ---------------------------------------------------------------------
        # PHẦN 4. LỊCH SỬ XỬ LÝ (KHOÁ / MỞ KHOÁ TÀI KHOẢN)
        # ---------------------------------------------------------------------
        self._draw_section_card_frame(c4, "PHẦN 4. LỊCH SỬ XỬ LÝ", "XỬ LÝ >", COLOR_STRIPE_B1, "part4")
        y4 = c4.y + 34
        locks = acc.get("lock_history") or []
        latest_lk = locks[0] if locks else None

        if st == "locked":
            cur_reason = acc.get("lock_reason") or (latest_lk.get("reason") if latest_lk else "Vi phạm quy định")
            cur_by = acc.get("locked_by") or (latest_lk.get("performed_by") if latest_lk else "admin")
            cur_time = acc.get("locked_at_str") if acc.get("locked_at_str") != "--" else (latest_lk.get("time_str") if latest_lk else "--")
            cur_dur = f"ĐANG KHOÁ ({acc.get('lock_duration_label', 'Vĩnh viễn')} -> {acc.get('locked_until_str', '--')})"
            st_lk_col = COLOR_RED
        elif latest_lk:
            cur_reason = latest_lk.get("reason", "--")
            cur_by = latest_lk.get("performed_by", "admin")
            cur_time = latest_lk.get("time_str", "--")
            cur_dur = f"{latest_lk.get('action', 'MỞ KHOÁ')} ({len(locks)} lần xử lý)"
            st_lk_col = (25, 150, 65)
        else:
            cur_reason = "Chưa từng bị khoá"
            cur_by = "admin"
            cur_time = "--"
            cur_dur = "Tài khoản trong sạch (0 lần khoá)"
            st_lk_col = (25, 150, 65)

        self._draw_kv_row(c4.x + 8, y4,       cw - 16, "1. Lịch sử khoá TK:", cur_dur, st_lk_col)
        self._draw_kv_row(c4.x + 8, y4 + 28,  cw - 16, "2. Lý do khoá:", cur_reason, COLOR_RED if st == "locked" else (60, 40, 25))
        self._draw_kv_row(c4.x + 8, y4 + 56,  cw - 16, "3. Người thực hiện:", cur_by.upper(), COLOR_PURPLE_BACK)
        self._draw_kv_row(c4.x + 8, y4 + 84,  cw - 16, "4. Thời gian xử lý:", cur_time)

        # Nút thao tác nhanh trong Phần 4
        b_lk1 = pygame.Rect(c4.x + 8, y4 + 112, (cw - 22) // 2, 24)
        b_lk2 = pygame.Rect(b_lk1.right + 6, y4 + 112, (cw - 22) // 2, 24)
        if st == "locked":
            self._draw_3d_button(b_lk1, "MỞ KHOÁ TK", (22, 168, 95), (255, 255, 255), (15, 120, 65), (10, 95, 50), radius=6)
            self.admin_click_areas.append((b_lk1, lambda u=acc["username"]: self._exec_admin_unlock(u)))
        else:
            self._draw_3d_button(b_lk1, "KHOÁ TÀI KHOẢN", COLOR_RED, (255, 255, 255), (165, 20, 45), (130, 10, 35), radius=6)
            self.admin_click_areas.append((b_lk1, lambda u=acc["username"]: self._open_admin_lock_modal(u)))

        self._draw_3d_button(b_lk2, "XEM DS BỊ KHOÁ", COLOR_SURFACE_ACTIVE, COLOR_TEXT_ORANGE, radius=6)
        self.admin_click_areas.append((b_lk2, lambda: self._set_admin_detail_tab("locked_list")))

    def _draw_admin_part1_expanded(self, area: pygame.Rect, acc: dict):
        self._draw_section_card_frame(area, "PHẦN 1. THÔNG TIN CÁ NHÂN (CHI TIẾT HỒ SƠ)", "< VỀ 4 PHẦN", COLOR_STRIPE_A1, "all_4")
        y = area.y + 42
        w = area.width - 24
        x = area.x + 12

        self._draw_kv_row(x, y,       w, "1. ID Người chơi (Player ID):", f"ID #{acc['id']}  •  Mã định danh: {acc['player_code']}", COLOR_PURPLE_BACK)
        self._draw_kv_row(x, y + 34,  w, "2. Tên đăng nhập (Username):", f"{acc['username']}  (Vai trò: {'Quản trị viên - ADMIN' if acc.get('role')=='admin' else 'Người chơi - USER'})", COLOR_TEXT_ORANGE)
        self._draw_kv_row(x, y + 68,  w, "3. Ngày tạo tài khoản:", f"{acc.get('created_at_str')}  ({'Đăng ký mới hôm nay' if acc.get('is_registered_today') else 'Tài khoản đã xác thực'})")
        st = acc.get("status", "active")
        st_col = COLOR_RED if st == "locked" else ((130, 105, 80) if st == "inactive" else (25, 155, 55))
        self._draw_kv_row(x, y + 102, w, "4. Trạng thái tài khoản:", f"{acc.get('status_vn', '').upper()}  •  Kết nối hiện tại: {'ĐANG ONLINE' if acc.get('is_online') else 'OFFLINE'}", st_col)

        pw_raw = str(acc.get("password") or "123456")
        pw_disp = pw_raw if self.admin_show_user_pw else ("*" * max(6, len(pw_raw)))
        self._draw_kv_row(x, y + 136, w - 110, "5. Mật khẩu đăng nhập:", pw_disp)
        btn_pw = pygame.Rect(x + w - 102, y + 136, 102, 24)
        self._draw_3d_button(btn_pw, "ẨN MẬT KHẨU" if self.admin_show_user_pw else "HIỆN MẬT KHẨU", COLOR_SURFACE_ACTIVE, COLOR_TEXT_ORANGE, radius=6)
        self.admin_click_areas.append((btn_pw, self._toggle_admin_user_pw))

        # Chuyển nhanh trạng thái tài khoản
        lbl_st = self.font_xs.render("ĐỔI NHANH TRẠNG THÁI TÀI KHOẢN:", False, COLOR_TEXT_ORANGE)
        self.screen.blit(lbl_st, (x, y + 178))

        b1 = pygame.Rect(x, y + 200, 180, 32)
        b2 = pygame.Rect(x + 190, y + 200, 180, 32)
        b3 = pygame.Rect(x + 380, y + 200, 180, 32)
        self._draw_3d_button(b1, "ĐẶT: ĐANG HOẠT ĐỘNG", (25, 165, 70), (255, 255, 255), (15, 120, 50), (10, 90, 35))
        self._draw_3d_button(b2, "ĐẶT: KHÔNG HOẠT ĐỘNG", (140, 110, 85), (255, 255, 255), (100, 75, 55), (80, 60, 40))
        self._draw_3d_button(b3, "KHOÁ TÀI KHOẢN NÀY", COLOR_RED, (255, 255, 255), (165, 20, 45), (130, 10, 35))
        self.admin_click_areas.append((b1, lambda: self._quick_set_status("active")))
        self.admin_click_areas.append((b2, lambda: self._quick_set_status("inactive")))
        self.admin_click_areas.append((b3, lambda u=acc["username"]: self._open_admin_lock_modal(u)))

    def _draw_admin_part2_expanded(self, area: pygame.Rect, acc: dict):
        self._draw_section_card_frame(area, "PHẦN 2. THÔNG TIN TRÒ CHƠI (CHỈ SỐ & NHÂN VẬT)", "< VỀ 4 PHẦN", COLOR_STRIPE_A2, "all_4")
        x = area.x + 12
        y = area.y + 40
        w = area.width - 24

        rows_spec = [
            ("1. Level hiện tại:", f"Cấp độ {acc['level']} (Thú cưng: {acc.get('pet_name', 'TAMA')})", "level", 1, COLOR_TEXT_ORANGE),
            ("2. Tổng điểm kinh nghiệm (XP):", f"{acc['total_xp']:,} XP", "total_xp", 100, COLOR_PURPLE_BACK),
            ("3. Tổng số tiền (Coin):", f"{acc['gold']:,} Coin ($)", "gold", 200, (210, 125, 0)),
            ("4. Số lượng nhân vật mở khoá:", f"{acc['unlocked_count']} Nhân vật Tamagotchi", "unlocked_count", 1, (25, 150, 65)),
            ("5. Chuỗi ngày duy trì (Streak):", f"{acc['streak_days']} Ngày liên tiếp", "streak_days", 1, COLOR_RED),
        ]
        for idx, (lbl, val_s, field_key, step, col) in enumerate(rows_spec):
            ry = y + idx * 34
            self._draw_kv_row(x, ry, w - 134, lbl, val_s, col)
            bm = pygame.Rect(x + w - 126, ry, 58, 24)
            bp = pygame.Rect(x + w - 62, ry, 62, 24)
            self._draw_3d_button(bm, f"-{step}", COLOR_SURFACE_SHADOW, COLOR_TEXT_ORANGE, radius=6)
            self._draw_3d_button(bp, f"+{step}", COLOR_SURFACE_ACTIVE, COLOR_PURPLE_BACK, radius=6)
            self.admin_click_areas.append((bm, lambda f=field_key, d=-step: self._quick_adjust_game_stat(f, d)))
            self.admin_click_areas.append((bp, lambda f=field_key, d=step: self._quick_adjust_game_stat(f, d)))

        # Bộ sưu tập nhân vật đã mở khoá
        gal_box = pygame.Rect(x, y + 180, w, area.bottom - (y + 190))
        pygame.draw.rect(self.screen, (255, 248, 238), gal_box, border_radius=9)
        pygame.draw.rect(self.screen, COLOR_BORDER, gal_box, 2, border_radius=9)
        self._draw_clipped_text(self.screen, self.font_xs, f"BỘ SƯU TẬP NHÂN VẬT ĐÃ MỞ KHOÁ ({acc['unlocked_count']} NHÂN VẬT):", COLOR_PURPLE_BACK, gal_box.x + 10, gal_box.y + 8, gal_box.width - 20)

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
        chars = list(acc.get("unlocked_characters") or [])
        while len(chars) < min(10, int(acc.get("unlocked_count") or 1)):
            chars.append(sample_pool[len(chars) % len(sample_pool)])

        frame_num = 1 if int(self.auth_anim_tick * 3.0) % 2 == 0 else 2
        cx = gal_box.x + 14
        for c_path in chars[:10]:
            c_card = pygame.Rect(cx, gal_box.y + 30, 52, 52)
            pygame.draw.rect(self.screen, (255, 255, 255), c_card, border_radius=8)
            pygame.draw.rect(self.screen, COLOR_BORDER, c_card, 1, border_radius=8)
            sp = self._get_admin_char_sprite(c_path, frame_num, 42)
            self.screen.blit(sp, (c_card.x + 5, c_card.y + 5))
            cx += 62

    def _draw_admin_part3_expanded(self, area: pygame.Rect, acc: dict):
        self._draw_section_card_frame(area, "PHẦN 3. HOẠT ĐỘNG TÀI KHOẢN & THIẾT BỊ", "< VỀ 4 PHẦN", COLOR_STRIPE_B2, "all_4")
        x = area.x + 12
        y = area.y + 38
        w = area.width - 24

        self._draw_kv_row(x, y,      w, "1. Lần đăng nhập cuối:", acc.get("last_login_str", "--"), COLOR_TEXT_ORANGE)
        self._draw_kv_row(x, y + 30, w, "2. Tổng số lần đăng nhập:", f"{acc.get('login_count', 1)} Lần đăng nhập", COLOR_PURPLE_BACK)
        self._draw_kv_row(x, y + 60, w, "4. Thiết bị đăng nhập:", acc.get("last_device", "Web Browser (Tamaweb WASM)"), (25, 145, 75))

        # Bảng 3. Lịch sử hoạt động chi tiết
        log_hdr = pygame.Rect(x, y + 94, w, 22)
        pygame.draw.rect(self.screen, COLOR_SURFACE_ACTIVE, log_hdr, border_radius=6)
        self._draw_clipped_text(self.screen, self.font_xs, "THỜI GIAN", (90, 45, 10), log_hdr.x + 8, log_hdr.y + 4, 130)
        self._draw_clipped_text(self.screen, self.font_xs, "3. LỊCH SỬ HOẠT ĐỘNG CHI TIẾT", (90, 45, 10), log_hdr.x + 150, log_hdr.y + 4, 310)
        self._draw_clipped_text(self.screen, self.font_xs, "THIẾT BỊ", (90, 45, 10), log_hdr.right - 165, log_hdr.y + 4, 155)

        acts = acc.get("activity_history") or []
        ay = log_hdr.bottom + 4
        for idx, act_item in enumerate(acts[:6]):
            r_bg = (255, 248, 240) if idx % 2 == 0 else (255, 255, 255)
            ar = pygame.Rect(x, ay, w, 24)
            pygame.draw.rect(self.screen, r_bg, ar, border_radius=5)
            pygame.draw.rect(self.screen, (240, 220, 195), ar, 1, border_radius=5)
            self._draw_clipped_text(self.screen, self.font_xs, act_item.get("time_str", "--"), (110, 75, 45), ar.x + 8, ar.y + 4, 136)
            self._draw_clipped_text(self.screen, self.font_xs, act_item.get("description", "--"), (40, 25, 10), ar.x + 150, ar.y + 4, 320)
            self._draw_clipped_text(self.screen, self.font_xs, act_item.get("device", "--"), COLOR_PURPLE_BACK, ar.right - 165, ar.y + 4, 158)
            ay += 27

    def _draw_admin_part4_expanded(self, area: pygame.Rect, acc: dict):
        self._draw_section_card_frame(area, "PHẦN 4. LỊCH SỬ XỬ LÝ & KHOÁ TÀI KHOẢN", "< VỀ 4 PHẦN", COLOR_STRIPE_B1, "all_4")
        x = area.x + 12
        y = area.y + 38
        w = area.width - 24

        st = acc.get("status", "active")
        status_banner = pygame.Rect(x, y, w, 58)
        pygame.draw.rect(self.screen, (255, 240, 242) if st == "locked" else (242, 255, 245), status_banner, border_radius=9)
        pygame.draw.rect(self.screen, COLOR_RED if st == "locked" else (45, 175, 75), status_banner, 2, border_radius=9)

        if st == "locked":
            t1 = f"TÀI KHOẢN ĐANG BỊ KHOÁ  •  THỜI HẠN: {acc.get('lock_duration_label', 'Vĩnh viễn')} (MỞ LÚC: {acc.get('locked_until_str', '--')})"
            t2 = f"Lý do khoá: {acc.get('lock_reason', '--')}  |  Người thực hiện: {acc.get('locked_by', 'admin').upper()}  |  Lúc: {acc.get('locked_at_str', '--')}"
            self._draw_clipped_text(self.screen, self.font_xs, t1, COLOR_RED, status_banner.x + 10, status_banner.y + 8, w - 180)
            self._draw_clipped_text(self.screen, self.font_xs, t2, (90, 30, 40), status_banner.x + 10, status_banner.y + 31, w - 180)
            btn_act = pygame.Rect(status_banner.right - 162, status_banner.y + 13, 152, 32)
            self._draw_3d_button(btn_act, "MỞ KHOÁ NGAY", (22, 168, 95), (255, 255, 255), (15, 120, 65), (10, 95, 50))
            self.admin_click_areas.append((btn_act, lambda u=acc["username"]: self._exec_admin_unlock(u)))
        else:
            t1 = "TÀI KHOẢN ĐANG HOẠT ĐỘNG BÌNH THƯỜNG (KHÔNG BỊ KHOÁ)"
            t2 = "Admin có thể khoá tài khoản, chọn lý do khoá và thiết lập thời hạn khoá bên phải."
            self._draw_clipped_text(self.screen, self.font_xs, t1, (25, 145, 65), status_banner.x + 10, status_banner.y + 8, w - 180)
            self._draw_clipped_text(self.screen, self.font_xs, t2, (80, 100, 85), status_banner.x + 10, status_banner.y + 31, w - 180)
            btn_act = pygame.Rect(status_banner.right - 162, status_banner.y + 13, 152, 32)
            self._draw_3d_button(btn_act, "KHOÁ TÀI KHOẢN", COLOR_RED, (255, 255, 255), (165, 20, 45), (130, 10, 35))
            self.admin_click_areas.append((btn_act, lambda u=acc["username"]: self._open_admin_lock_modal(u)))

        # Bảng lịch sử xử lý (1. Lịch sử khoá, 2. Lý do khoá, 3. Người thực hiện, 4. Thời gian xử lý)
        hdr = pygame.Rect(x, y + 66, w, 24)
        pygame.draw.rect(self.screen, COLOR_SURFACE_ACTIVE, hdr, border_radius=6)
        self._draw_clipped_text(self.screen, self.font_xs, "4. THỜI GIAN XỬ LÝ", (90, 45, 10), hdr.x + 8, hdr.y + 4, 130)
        self._draw_clipped_text(self.screen, self.font_xs, "1. THAO TÁC / THỜI HẠN", (90, 45, 10), hdr.x + 145, hdr.y + 4, 155)
        self._draw_clipped_text(self.screen, self.font_xs, "2. LÝ DO KHOÁ / XỬ LÝ", (90, 45, 10), hdr.x + 308, hdr.y + 4, 240)
        self._draw_clipped_text(self.screen, self.font_xs, "3. NGƯỜI THỰC HIỆN", (90, 45, 10), hdr.right - 115, hdr.y + 4, 110)

        locks = acc.get("lock_history") or []
        ly = hdr.bottom + 5
        if not locks:
            empty_s = self.font_xs.render("TÀI KHOẢN NÀY CHƯA CÓ LỊCH SỬ BỊ KHOÁ / XỬ LÝ VI PHẠM.", False, (130, 100, 75))
            self.screen.blit(empty_s, (area.centerx - empty_s.get_width() // 2, ly + 45))
        else:
            for idx, lk in enumerate(locks[:7]):
                lr = pygame.Rect(x, ly, w, 26)
                is_lock_act = ("KHOÁ" in lk.get("action", "") and "MỞ" not in lk.get("action", ""))
                pygame.draw.rect(self.screen, (255, 245, 246) if is_lock_act else (245, 255, 248), lr, border_radius=5)
                pygame.draw.rect(self.screen, (235, 195, 200) if is_lock_act else (195, 230, 205), lr, 1, border_radius=5)

                self._draw_clipped_text(self.screen, self.font_xs, lk.get("time_str", "--"), (95, 65, 40), lr.x + 8, lr.y + 5, 132)
                act_dur = f"{lk.get('action', '')} ({lk.get('duration_label', '--')})"
                self._draw_clipped_text(self.screen, self.font_xs, act_dur, COLOR_RED if is_lock_act else (20, 150, 65), lr.x + 145, lr.y + 5, 158)
                self._draw_clipped_text(self.screen, self.font_xs, lk.get("reason", "--"), (40, 25, 15), lr.x + 308, lr.y + 5, 242)
                self._draw_clipped_text(self.screen, self.font_xs, lk.get("performed_by", "admin").upper(), COLOR_PURPLE_BACK, lr.right - 105, lr.y + 5, 98)
                ly += 29

    def _draw_admin_locked_accounts_table(self, area: pygame.Rect):
        """Hiển thị danh sách toàn bộ các tài khoản đang bị khoá kèm lý do, thời hạn và nút Mở khoá"""
        locked_list = [a for a in self.admin_accounts if a.get("status") == "locked"]
        self._draw_section_card_frame(
            area,
            f"DANH SÁCH TÀI KHOẢN ĐANG BỊ KHOÁ ({len(locked_list)} TÀI KHOẢN)",
            "< VỀ 4 PHẦN",
            COLOR_STRIPE_B1,
            "all_4",
        )
        x = area.x + 10
        y = area.y + 36
        w = area.width - 20

        hdr = pygame.Rect(x, y, w, 24)
        pygame.draw.rect(self.screen, COLOR_SURFACE_ACTIVE, hdr, border_radius=6)
        self._draw_clipped_text(self.screen, self.font_xs, "ID / USERNAME", (90, 45, 10), hdr.x + 8, hdr.y + 4, 125)
        self._draw_clipped_text(self.screen, self.font_xs, "LÝ DO KHOÁ", (90, 45, 10), hdr.x + 138, hdr.y + 4, 210)
        self._draw_clipped_text(self.screen, self.font_xs, "THỜI HẠN / MỞ LÚC", (90, 45, 10), hdr.x + 355, hdr.y + 4, 155)
        self._draw_clipped_text(self.screen, self.font_xs, "NGƯỜI XỬ LÝ", (90, 45, 10), hdr.x + 515, hdr.y + 4, 80)
        self._draw_clipped_text(self.screen, self.font_xs, "THAO TÁC", (90, 45, 10), hdr.right - 78, hdr.y + 4, 72)

        ry = hdr.bottom + 6
        if not locked_list:
            msg = self.font_sm.render("HIỆN TẠI KHÔNG CÓ TÀI KHOẢN NÀO BỊ KHOÁ!", False, (25, 155, 65))
            self.screen.blit(msg, (area.centerx - msg.get_width() // 2, area.centery - 10))
            return

        for acc in locked_list[:7]:
            r_rect = pygame.Rect(x, ry, w, 38)
            pygame.draw.rect(self.screen, (255, 244, 246), r_rect, border_radius=8)
            pygame.draw.rect(self.screen, COLOR_RED, r_rect, 1, border_radius=8)

            self._draw_clipped_text(self.screen, self.font_xs, f"#{acc['id']} {acc['username'].upper()}", COLOR_PURPLE_BACK, r_rect.x + 8, r_rect.y + 4, 125)
            self._draw_clipped_text(self.screen, self.font_xs, f"Lúc: {acc.get('locked_at_str', '--')}", (120, 85, 65), r_rect.x + 8, r_rect.y + 20, 125)

            self._draw_clipped_text(self.screen, self.font_xs, acc.get("lock_reason") or "Vi phạm quy định", COLOR_RED, r_rect.x + 138, r_rect.y + 11, 210)

            dur_info = f"{acc.get('lock_duration_label', 'Vĩnh viễn')} ({acc.get('locked_until_str', '--')})"
            self._draw_clipped_text(self.screen, self.font_xs, dur_info, (70, 35, 15), r_rect.x + 355, r_rect.y + 11, 155)

            self._draw_clipped_text(self.screen, self.font_xs, (acc.get("locked_by") or "admin").upper(), COLOR_PURPLE_BACK, r_rect.x + 520, r_rect.y + 11, 75)

            btn_unlk = pygame.Rect(r_rect.right - 86, r_rect.y + 6, 80, 26)
            self._draw_3d_button(btn_unlk, "MỞ KHOÁ", (22, 168, 95), (255, 255, 255), (15, 120, 65), (10, 95, 50), radius=6)
            uname_val = acc["username"]
            self.admin_click_areas.append((btn_unlk, lambda u=uname_val: self._exec_admin_unlock(u)))
            ry += 43

    # =========================================================================
    # VẼ HỘP THOẠI MODAL (KHOÁ TÀI KHOẢN / THÊM / SỬA / XOÁ)
    # =========================================================================
    def _draw_admin_modal_overlay(self):
        dim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        dim.fill((35, 18, 8, 145))
        self.screen.blit(dim, (0, 0))

        if self.admin_modal == "lock":
            self._draw_admin_lock_modal()
        elif self.admin_modal in ("add", "edit"):
            self._draw_admin_add_edit_modal()
        elif self.admin_modal == "delete":
            self._draw_admin_delete_modal()

    def _draw_admin_lock_modal(self):
        acc = self._get_selected_admin_account()
        if not acc:
            return
        mw, mh = 540, 410
        mrect = pygame.Rect((WIN_W - mw) // 2, (WIN_H - mh) // 2, mw, mh)
        pygame.draw.rect(self.screen, (80, 35, 15), mrect.move(0, 6), border_radius=16)
        pygame.draw.rect(self.screen, COLOR_SURFACE, mrect, border_radius=16)
        pygame.draw.rect(self.screen, COLOR_RED, mrect, 4, border_radius=16)

        hdr = pygame.Rect(mrect.x + 12, mrect.y + 12, mw - 24, 38)
        pygame.draw.rect(self.screen, COLOR_RED, hdr, border_radius=10)
        self._draw_clipped_text(
            self.screen,
            self.font_md,
            f"KHOÁ TÀI KHOẢN: @{acc['username'].upper()} (#{acc['id']})",
            (255, 255, 255),
            hdr.centerx,
            hdr.y + 9,
            mw - 40,
            align="center",
        )

        # 1. Chọn nhanh Lý do khoá
        lbl1 = self.font_xs.render("1. CHỌN NHANH HOẶC NHẬP LÝ DO KHOÁ TÀI KHOẢN:", False, COLOR_TEXT_ORANGE)
        self.screen.blit(lbl1, (mrect.x + 20, mrect.y + 60))

        preset_reasons = [
            "Gian lận Coin & XP (Cheat/Hack)",
            "Spam / Lạm dụng lỗi hệ thống",
            "Vi phạm quy định cộng đồng",
            "Tài khoản nghi vấn bảo mật",
        ]
        for idx, r_txt in enumerate(preset_reasons):
            rx = mrect.x + 20 + (idx % 2) * 252
            ry = mrect.y + 82 + (idx // 2) * 32
            rb = pygame.Rect(rx, ry, 246, 27)
            sel = (self.admin_form.get("lock_reason") == r_txt)
            pygame.draw.rect(self.screen, COLOR_TEXT_ORANGE if sel else COLOR_SURFACE_SHADOW, rb, border_radius=7)
            pygame.draw.rect(self.screen, COLOR_BORDER, rb, 2 if sel else 1, border_radius=7)
            self._draw_clipped_text(self.screen, self.font_xs, r_txt, (255, 255, 255) if sel else (75, 40, 15), rb.centerx, rb.y + 5, 236, align="center")
            self.admin_modal_click_areas.append((rb, lambda t=r_txt: self._set_lock_reason(t)))

        # Ô nhập Lý do khoá tuỳ chỉnh
        box_reason = pygame.Rect(mrect.x + 20, mrect.y + 152, mw - 40, 36)
        blink = "|" if int(self.auth_anim_tick * 2.5) % 2 == 0 else ""
        self._draw_auth_input_box(
            box_reason,
            text=self.admin_form.get("lock_reason", "") + blink,
            placeholder="Nhập lý do khoá tài khoản...",
            focused=True,
            is_empty=(len(self.admin_form.get("lock_reason", "")) == 0),
        )

        # 2. Thiết lập thời hạn khoá
        lbl2 = self.font_xs.render("2. THIẾT LẬP THỜI HẠN KHOÁ TÀI KHOẢN:", False, COLOR_TEXT_ORANGE)
        self.screen.blit(lbl2, (mrect.x + 20, mrect.y + 202))

        durations = [
            ("1h", "1 GIỜ"),
            ("24h", "24 GIỜ (1 NGÀY)"),
            ("3d", "3 NGÀY"),
            ("7d", "7 NGÀY"),
            ("30d", "30 NGÀY"),
            ("permanent", "VĨNH VIỄN"),
        ]
        for idx, (d_key, d_lbl) in enumerate(durations):
            dx = mrect.x + 20 + (idx % 3) * 168
            dy = mrect.y + 224 + (idx // 3) * 36
            db = pygame.Rect(dx, dy, 160, 30)
            sel = (self.admin_form.get("lock_duration_key") == d_key)
            pygame.draw.rect(self.screen, COLOR_PURPLE_BACK if sel else COLOR_SURFACE_SHADOW, db, border_radius=8)
            pygame.draw.rect(self.screen, COLOR_BORDER, db, 2 if sel else 1, border_radius=8)
            self._draw_clipped_text(self.screen, self.font_xs, d_lbl, (255, 255, 255) if sel else (75, 40, 15), db.centerx, db.y + 7, 150, align="center")
            self.admin_modal_click_areas.append((db, lambda k=d_key: self._set_lock_duration(k)))

        info_line = f"Người thực hiện thao tác: ADMIN ({self.backend.user_id})  •  Ghi nhận tự động vào Phần 4 (Lịch sử xử lý)"
        self._draw_clipped_text(self.screen, self.font_xs, info_line, (110, 75, 45), mrect.centerx, mrect.y + 308, mw - 40, align="center")

        btn_confirm = pygame.Rect(mrect.x + 20, mrect.bottom - 58, 310, 42)
        btn_cancel = pygame.Rect(btn_confirm.right + 12, mrect.bottom - 58, 178, 42)
        self._draw_3d_button(btn_confirm, "XÁC NHẬN KHOÁ TÀI KHOẢN", COLOR_RED, (255, 255, 255), (165, 20, 45), (125, 10, 30), font=self.font_sm, radius=10)
        self._draw_3d_button(btn_cancel, "HUỶ BỎ", COLOR_SURFACE_SHADOW, COLOR_TEXT_ORANGE, font=self.font_sm, radius=10)
        self.admin_modal_click_areas.append((btn_confirm, self._submit_admin_lock))
        self.admin_modal_click_areas.append((btn_cancel, self._close_admin_modal))

    def _draw_admin_add_edit_modal(self):
        is_add = (self.admin_modal == "add")
        mw, mh = 580, 468
        mrect = pygame.Rect((WIN_W - mw) // 2, (WIN_H - mh) // 2, mw, mh)
        pygame.draw.rect(self.screen, (80, 35, 15), mrect.move(0, 6), border_radius=16)
        pygame.draw.rect(self.screen, COLOR_SURFACE, mrect, border_radius=16)
        pygame.draw.rect(self.screen, COLOR_BORDER, mrect, 4, border_radius=16)

        hdr = pygame.Rect(mrect.x + 12, mrect.y + 12, mw - 24, 36)
        pygame.draw.rect(self.screen, COLOR_GREEN if is_add else COLOR_TEXT_ORANGE, hdr, border_radius=10)
        h_title = "THÊM TÀI KHOẢN NGƯỜI CHƠI MỚI" if is_add else f"CHỈNH SỬA TÀI KHOẢN: @{self.admin_selected_username.upper()}"
        self._draw_clipped_text(self.screen, self.font_md, h_title, (255, 255, 255), hdr.centerx, hdr.y + 8, mw - 36, align="center")

        fields = [
            (0, "username",       "1. TÀI KHOẢN (USERNAME):",      is_add),
            (1, "password",       "2. MẬT KHẨU (PASSWORD):",       True),
            (2, "level",          "3. LEVEL HIỆN TẠI:",            True),
            (3, "total_xp",       "4. TỔNG ĐIỂM XP:",              True),
            (4, "gold",           "5. TỔNG COIN ($):",             True),
            (5, "unlocked_count", "6. SỐ NHÂN VẬT MỞ KHOÁ:",       True),
            (6, "streak_days",    "7. CHUỖI NGÀY DUY TRÌ:",        True),
            (7, "last_device",    "8. THIẾT BỊ ĐĂNG NHẬP:",        True),
        ]

        blink = "|" if int(self.auth_anim_tick * 2.5) % 2 == 0 else ""
        for idx, f_key, f_lbl, editable in fields:
            col_i = idx % 2
            row_i = idx // 2
            fx = mrect.x + 20 + col_i * 276
            fy = mrect.y + 58 + row_i * 68

            self._draw_clipped_text(self.screen, self.font_xs, f_lbl, COLOR_TEXT_ORANGE, fx, fy, 260)
            box = pygame.Rect(fx, fy + 18, 264, 34)
            focused = (self.admin_modal_focus == idx and editable)
            val_str = str(self.admin_form.get(f_key, ""))
            pygame.draw.rect(self.screen, (255, 255, 255) if editable else (240, 232, 222), box, border_radius=8)
            pygame.draw.rect(self.screen, COLOR_PURPLE_BACK if focused else COLOR_BORDER, box, 3 if focused else 2, border_radius=8)
            self._draw_clipped_text(self.screen, self.font_sm, val_str + (blink if focused else ""), (35, 20, 10), box.x + 10, box.y + 7, box.width - 20)
            if editable:
                self.admin_modal_click_areas.append((box, lambda i=idx: self._set_admin_modal_focus(i)))

        # Chọn trạng thái tài khoản
        st_y = mrect.y + 338
        self._draw_clipped_text(self.screen, self.font_xs, "9. TRẠNG THÁI TÀI KHOẢN:", COLOR_TEXT_ORANGE, mrect.x + 20, st_y, 220)
        for idx, (st_key, st_lbl, st_col) in enumerate([
            ("active", "ĐANG HOẠT ĐỘNG", (35, 165, 65)),
            ("inactive", "KHÔNG HOẠT ĐỘNG", (140, 110, 85)),
            ("locked", "TÀI KHOẢN BỊ KHOÁ", COLOR_RED),
        ]):
            sb = pygame.Rect(mrect.x + 20 + idx * 182, st_y + 20, 174, 30)
            sel = (self.admin_form.get("status") == st_key)
            pygame.draw.rect(self.screen, st_col if sel else COLOR_SURFACE_SHADOW, sb, border_radius=8)
            pygame.draw.rect(self.screen, COLOR_BORDER, sb, 2 if sel else 1, border_radius=8)
            self._draw_clipped_text(self.screen, self.font_xs, st_lbl, (255, 255, 255) if sel else (75, 40, 15), sb.centerx, sb.y + 7, 164, align="center")
            self.admin_modal_click_areas.append((sb, lambda s=st_key: self._set_form_status(s)))

        btn_save = pygame.Rect(mrect.x + 20, mrect.bottom - 56, 340, 40)
        btn_cancel = pygame.Rect(btn_save.right + 12, mrect.bottom - 56, 188, 40)
        self._draw_3d_button(btn_save, "LƯU THÔNG TIN TÀI KHOẢN", COLOR_GREEN, (255, 255, 255), (35, 135, 25), (25, 100, 15), font=self.font_sm, radius=10)
        self._draw_3d_button(btn_cancel, "HUỶ BỎ", COLOR_SURFACE_SHADOW, COLOR_TEXT_ORANGE, font=self.font_sm, radius=10)
        self.admin_modal_click_areas.append((btn_save, self._submit_admin_add_or_edit))
        self.admin_modal_click_areas.append((btn_cancel, self._close_admin_modal))

    def _draw_admin_delete_modal(self):
        acc = self._get_selected_admin_account()
        if not acc:
            return
        mw, mh = 460, 230
        mrect = pygame.Rect((WIN_W - mw) // 2, (WIN_H - mh) // 2, mw, mh)
        pygame.draw.rect(self.screen, (80, 35, 15), mrect.move(0, 6), border_radius=16)
        pygame.draw.rect(self.screen, COLOR_SURFACE, mrect, border_radius=16)
        pygame.draw.rect(self.screen, COLOR_RED, mrect, 4, border_radius=16)

        self._draw_clipped_text(self.screen, self.font_md, "XÁC NHẬN XOÁ TÀI KHOẢN?", COLOR_RED, mrect.centerx, mrect.y + 22, mw - 30, align="center")
        self._draw_clipped_text(
            self.screen,
            self.font_sm,
            f"Tài khoản: @{acc['username'].upper()} (ID #{acc['id']})",
            COLOR_PURPLE_BACK,
            mrect.centerx,
            mrect.y + 62,
            mw - 30,
            align="center",
        )
        self._draw_clipped_text(
            self.screen,
            self.font_xs,
            "Toàn bộ dữ liệu cá nhân, thú cưng, coin và lịch sử sẽ bị xoá vĩnh viễn!",
            (95, 55, 30),
            mrect.centerx,
            mrect.y + 98,
            mw - 30,
            align="center",
        )

        btn_yes = pygame.Rect(mrect.x + 24, mrect.bottom - 62, 230, 42)
        btn_no = pygame.Rect(btn_yes.right + 14, mrect.bottom - 62, 168, 42)
        self._draw_3d_button(btn_yes, "XÁC NHẬN XOÁ", COLOR_RED, (255, 255, 255), (165, 20, 45), (125, 10, 30), font=self.font_sm, radius=10)
        self._draw_3d_button(btn_no, "HUỶ BỎ", COLOR_SURFACE_SHADOW, COLOR_TEXT_ORANGE, font=self.font_sm, radius=10)
        self.admin_modal_click_areas.append((btn_yes, self._submit_admin_delete))
        self.admin_modal_click_areas.append((btn_no, self._close_admin_modal))

    def _toggle_locked_accounts_view(self):
        self.sound.play("click")
        if self.admin_detail_tab == "locked_list":
            self.admin_detail_tab = "all_4"
            self.admin_filter = "all"
        else:
            self.admin_detail_tab = "locked_list"
            self.admin_filter = "locked"
            self.admin_page = 0

    def _manual_refresh_admin(self):
        self.sound.play("confirm")
        self._refresh_admin_dashboard(keep_selection=True)
        self._set_admin_notice("ĐÃ LÀM MỚI DỮ LIỆU TÀI KHOẢN TỪ HỆ THỐNG!", COLOR_GREEN)

    def _focus_admin_search(self):
        self.sound.play("click")
        self.admin_search_focused = True

    def _clear_admin_search(self):
        self.sound.play("click")
        self.admin_search_query = ""
        self.admin_search_focused = False
        self.admin_page = 0

    def _change_admin_page(self, delta: int):
        self.sound.play("click")
        filtered = self._get_filtered_admin_accounts()
        total_pages = max(1, (len(filtered) + 6) // 7)
        self.admin_page = max(0, min(total_pages - 1, self.admin_page + delta))

    def _toggle_admin_user_pw(self):
        self.sound.play("click")
        self.admin_show_user_pw = not self.admin_show_user_pw

    def _quick_set_status(self, new_status: str):
        acc = self._get_selected_admin_account()
        if not acc:
            return
        if acc["username"] == "admin" and new_status != "active":
            self.sound.play("refuse")
            self._set_admin_notice("KHÔNG THỂ ĐỔI TRẠNG THÁI CỦA ADMIN GỐC!", COLOR_RED)
            return
        ok, msg, _ = self.backend.admin_update_account(acc["username"], {"status": new_status})
        if ok:
            self.sound.play("confirm")
            self._refresh_admin_dashboard(keep_selection=True)
            self._set_admin_notice(msg, COLOR_GREEN)

    def _set_lock_reason(self, reason: str):
        self.sound.play("click")
        self.admin_form["lock_reason"] = reason

    def _set_lock_duration(self, d_key: str):
        self.sound.play("click")
        self.admin_form["lock_duration_key"] = d_key

    def _set_admin_modal_focus(self, idx: int):
        self.sound.play("click")
        self.admin_modal_focus = idx

    def _set_form_status(self, st: str):
        self.sound.play("click")
        self.admin_form["status"] = st

    def _handle_admin_keydown(self, event: pygame.event.Event):
        if self.admin_modal == "lock":
            if event.key == pygame.K_ESCAPE:
                self._close_admin_modal()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._submit_admin_lock()
            elif event.key == pygame.K_BACKSPACE:
                self.sound.play("click")
                self.admin_form["lock_reason"] = self.admin_form.get("lock_reason", "")[:-1]
            else:
                ch = event.unicode
                if ch and ch.isprintable() and ch not in ("\r", "\n", "\t") and len(self.admin_form.get("lock_reason", "")) < 48:
                    self.sound.play("click")
                    self.admin_form["lock_reason"] = self.admin_form.get("lock_reason", "") + ch
            return

        if self.admin_modal in ("add", "edit"):
            field_keys = ["username", "password", "level", "total_xp", "gold", "unlocked_count", "streak_days", "last_device"]
            numeric_keys = {"level", "total_xp", "gold", "unlocked_count", "streak_days"}
            min_idx = 0 if self.admin_modal == "add" else 1
            if self.admin_modal_focus < min_idx:
                self.admin_modal_focus = min_idx
            cur_key = field_keys[self.admin_modal_focus % len(field_keys)]

            if event.key == pygame.K_ESCAPE:
                self._close_admin_modal()
            elif event.key == pygame.K_TAB:
                self.sound.play("click")
                nxt = (self.admin_modal_focus + 1) % len(field_keys)
                if nxt < min_idx:
                    nxt = min_idx
                self.admin_modal_focus = nxt
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._submit_admin_add_or_edit()
            elif event.key == pygame.K_BACKSPACE:
                self.sound.play("click")
                self.admin_form[cur_key] = str(self.admin_form.get(cur_key, ""))[:-1]
            else:
                ch = event.unicode
                if ch and ch.isprintable() and ch not in ("\r", "\n", "\t"):
                    if cur_key in numeric_keys and not ch.isdigit():
                        return
                    if len(str(self.admin_form.get(cur_key, ""))) < 28:
                        self.sound.play("click")
                        self.admin_form[cur_key] = str(self.admin_form.get(cur_key, "")) + ch
            return

        if self.admin_modal == "delete":
            if event.key == pygame.K_ESCAPE:
                self._close_admin_modal()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._submit_admin_delete()
            return

        if self.admin_search_focused:
            if event.key == pygame.K_ESCAPE:
                self.admin_search_focused = False
            elif event.key == pygame.K_BACKSPACE:
                self.sound.play("click")
                self.admin_search_query = self.admin_search_query[:-1]
                self.admin_page = 0
            else:
                ch = event.unicode
                if ch and ch.isprintable() and ch not in ("\r", "\n", "\t") and len(self.admin_search_query) < 24:
                    self.sound.play("click")
                    self.admin_search_query += ch
                    self.admin_page = 0
            return

        # Phím tắt điều hướng danh sách tài khoản bằng mũi tên Lên / Xuống
        filtered = self._get_filtered_admin_accounts()
        if not filtered:
            return
        usernames = [a["username"] for a in filtered]
        cur_idx = usernames.index(self.admin_selected_username) if self.admin_selected_username in usernames else 0
        if event.key == pygame.K_DOWN:
            self.sound.play("click")
            new_idx = min(len(usernames) - 1, cur_idx + 1)
            self.admin_selected_username = usernames[new_idx]
            self.admin_page = new_idx // 7
        elif event.key == pygame.K_UP:
            self.sound.play("click")
            new_idx = max(0, cur_idx - 1)
            self.admin_selected_username = usernames[new_idx]
            self.admin_page = new_idx // 7

    def _draw_auth_screen(self):
        self.auth_click_areas.clear()

        # Logo Tamaweb chính hãng ở đỉnh thẻ
        logo_top = pygame.transform.smoothscale(self.logo_img, (195, 80))
        self.screen.blit(logo_top, ((WIN_W - logo_top.get_width()) // 2, 48))

        # Tính chiều cao thẻ vừa khít nội dung (không có khung thừa), căn giữa màn hình 1280x720
        extra_reg_h = 64 if self.auth_mode == "register" else 0
        extra_err_h = 34 if self.auth_msg else 0
        card_w = 384
        card_h = 382 + extra_reg_h + extra_err_h
        card_y = 140 if self.auth_mode == "register" else 160
        card = pygame.Rect((WIN_W - card_w) // 2, card_y, card_w, card_h)
        pygame.draw.rect(self.screen, (110, 65, 25, 85), card.move(0, 8), border_radius=18)
        pygame.draw.rect(self.screen, COLOR_SURFACE_SHADOW, card.move(0, 5), border_radius=18)
        pygame.draw.rect(self.screen, COLOR_SURFACE, card, border_radius=18)
        pygame.draw.rect(self.screen, COLOR_BORDER, card, 4, border_radius=18)

        # Banner cảnh công viên Pixel Tamaweb + 4 nhân vật Tamagotchi nhún nhảy
        banner_rect = pygame.Rect(card.x + 14, card.y + 14, card.width - 28, 82)
        banner_surf = pygame.Surface((banner_rect.width, banner_rect.height))
        sky_scaled = pygame.transform.scale(self.get_current_sky(), (banner_rect.width, banner_rect.height))
        park_scaled = pygame.transform.scale(self.scene_bgs["park"], (banner_rect.width, banner_rect.height + 24))
        banner_surf.blit(sky_scaled, (0, 0))
        banner_surf.blit(park_scaled, (0, -16))

        frame_num = 1 if int(self.auth_anim_tick * 3.0) % 2 == 0 else 2
        bounce_offsets = [0, -3, 0, -2]
        for idx, sheet in enumerate(self.auth_mascots):
            dy = bounce_offsets[(idx + int(self.auth_anim_tick * 4)) % 4]
            char_frame = pygame.transform.scale(sheet.get_frame(frame_num), (52, 52))
            cx = 24 + idx * 82
            cy = 24 + dy
            banner_surf.blit(char_frame, (cx, cy))
            # Tim hồng bay lơ lửng phía trên nhân vật
            heart_y = 8 + int(math.sin(self.auth_anim_tick * 4.0 + idx) * 4)
            heart_sc = pygame.transform.scale(self.pet.heart1_img, (14, 14))
            banner_surf.blit(heart_sc, (cx + 20, heart_y))

        self.screen.blit(banner_surf, banner_rect.topleft)
        pygame.draw.rect(self.screen, COLOR_BORDER, banner_rect, 3, border_radius=10)

        # 2 Nút chuyển chế độ: ĐĂNG NHẬP | ĐĂNG KÝ MỚI
        tab_y = banner_rect.bottom + 12
        tab_w = (card.width - 36) // 2
        btn_tab_login = pygame.Rect(card.x + 14, tab_y, tab_w, 34)
        btn_tab_reg = pygame.Rect(card.x + 22 + tab_w, tab_y, tab_w, 34)

        for t_rect, mode_key, label in [
            (btn_tab_login, "login", "ĐĂNG NHẬP"),
            (btn_tab_reg, "register", "ĐĂNG KÝ MỚI"),
        ]:
            active = self.auth_mode == mode_key
            bg_col = COLOR_TEXT_ORANGE if active else COLOR_SURFACE_SHADOW
            fg_col = (255, 255, 255) if active else COLOR_TEXT_ORANGE
            pygame.draw.rect(self.screen, COLOR_BORDER, t_rect.move(0, 3), border_radius=10)
            pygame.draw.rect(self.screen, bg_col, t_rect, border_radius=10)
            pygame.draw.rect(self.screen, COLOR_BORDER, t_rect, 2, border_radius=10)
            t_surf = self.font_sm.render(label, False, fg_col)
            self.screen.blit(t_surf, (t_rect.centerx - t_surf.get_width() // 2, t_rect.centery - t_surf.get_height() // 2))
            self.auth_click_areas.append((t_rect, lambda m=mode_key: self._switch_auth_mode(m)))

        # Các ô nhập liệu (Tài khoản, Mật khẩu, và Nhập lại mật khẩu khi Đăng ký)
        cursor_blink = "|" if int(self.auth_anim_tick * 2.5) % 2 == 0 else ""

        # Ô 1: TÀI KHOẢN
        lbl_u = self.font_xs.render("TÀI KHOẢN (USERNAME):", False, COLOR_TEXT_ORANGE)
        self.screen.blit(lbl_u, (card.x + 20, tab_y + 46))
        box_u = pygame.Rect(card.x + 18, tab_y + 64, card.width - 36, 36)
        self._draw_auth_input_box(
            box_u,
            text=self.auth_username + (cursor_blink if self.auth_focus == 0 else ""),
            placeholder="Nhập tên tài khoản...",
            focused=(self.auth_focus == 0),
            is_empty=(len(self.auth_username) == 0),
        )
        self.auth_click_areas.append((box_u, lambda: self._set_auth_focus(0)))

        # Ô 2: MẬT KHẨU + Nút [HIỆN/ẨN]
        lbl_p = self.font_xs.render("MẬT KHẨU (PASSWORD):", False, COLOR_TEXT_ORANGE)
        self.screen.blit(lbl_p, (card.x + 20, tab_y + 110))
        box_p = pygame.Rect(card.x + 18, tab_y + 128, card.width - 102, 36)
        disp_pw = self.auth_password if self.auth_show_pw else ("*" * len(self.auth_password))
        self._draw_auth_input_box(
            box_p,
            text=disp_pw + (cursor_blink if self.auth_focus == 1 else ""),
            placeholder="Nhập mật khẩu...",
            focused=(self.auth_focus == 1),
            is_empty=(len(self.auth_password) == 0),
        )
        self.auth_click_areas.append((box_p, lambda: self._set_auth_focus(1)))

        btn_eye = pygame.Rect(box_p.right + 6, box_p.y, 60, 36)
        pygame.draw.rect(self.screen, COLOR_BORDER, btn_eye.move(0, 2), border_radius=8)
        pygame.draw.rect(self.screen, COLOR_SURFACE_ACTIVE if self.auth_show_pw else COLOR_SURFACE_SHADOW, btn_eye, border_radius=8)
        pygame.draw.rect(self.screen, COLOR_BORDER, btn_eye, 2, border_radius=8)
        eye_txt = self.font_xs.render("ẨN" if self.auth_show_pw else "HIỆN", False, COLOR_TEXT_ORANGE)
        self.screen.blit(eye_txt, (btn_eye.centerx - eye_txt.get_width() // 2, btn_eye.centery - eye_txt.get_height() // 2))
        self.auth_click_areas.append((btn_eye, self._toggle_show_pw))

        next_y = tab_y + 178

        # Ô 3: NHẬP LẠI MẬT KHẨU (Khi ở chế độ Đăng ký)
        if self.auth_mode == "register":
            lbl_c = self.font_xs.render("NHẬP LẠI MẬT KHẨU:", False, COLOR_TEXT_ORANGE)
            self.screen.blit(lbl_c, (card.x + 20, tab_y + 174))
            box_c = pygame.Rect(card.x + 18, tab_y + 192, card.width - 36, 36)
            disp_cf = self.auth_confirm if self.auth_show_pw else ("*" * len(self.auth_confirm))
            self._draw_auth_input_box(
                box_c,
                text=disp_cf + (cursor_blink if self.auth_focus == 2 else ""),
                placeholder="Nhập lại mật khẩu...",
                focused=(self.auth_focus == 2),
                is_empty=(len(self.auth_confirm) == 0),
            )
            self.auth_click_areas.append((box_c, lambda: self._set_auth_focus(2)))
            next_y = tab_y + 242

        # Chỉ hiển thị thông báo khi có lỗi nhập liệu / sai mật khẩu
        if self.auth_msg:
            msg_box = pygame.Rect(card.x + 18, next_y, card.width - 36, 26)
            pygame.draw.rect(self.screen, (255, 240, 242), msg_box, border_radius=7)
            pygame.draw.rect(self.screen, self.auth_msg_color, msg_box, 2, border_radius=7)
            m_surf = self.font_xs.render(self.auth_msg[:38], False, self.auth_msg_color)
            self.screen.blit(m_surf, (msg_box.centerx - m_surf.get_width() // 2, msg_box.centery - m_surf.get_height() // 2))
            next_y += 34

        # Nút Hành động chính
        btn_submit = pygame.Rect(card.x + 18, next_y, card.width - 36, 44)
        if self.auth_in_progress:
            dots = "." * ((int(self.auth_anim_tick * 3) % 3) + 1)
            sub_col = (180, 150, 130)
            sub_shadow = (140, 115, 95)
            sub_label = f"ĐANG XÁC THỰC{dots}"
        else:
            sub_col = COLOR_GREEN if self.auth_mode == "register" else COLOR_TEXT_ORANGE
            sub_shadow = (45, 145, 30) if self.auth_mode == "register" else (190, 85, 0)
            sub_label = "ĐĂNG KÝ & VÀO GAME" if self.auth_mode == "register" else "ĐĂNG NHẬP VÀO GAME"

        pygame.draw.rect(self.screen, sub_shadow, btn_submit.move(0, 4), border_radius=12)
        pygame.draw.rect(self.screen, sub_col, btn_submit, border_radius=12)
        pygame.draw.rect(self.screen, (255, 255, 255), btn_submit, 2, border_radius=12)
        sub_surf = self.font_md.render(sub_label, False, (255, 255, 255))
        self.screen.blit(sub_surf, (btn_submit.centerx - sub_surf.get_width() // 2, btn_submit.centery - sub_surf.get_height() // 2))
        if not self.auth_in_progress:
            self.auth_click_areas.append((btn_submit.inflate(14, 14), self._submit_auth))

        # Dòng chuyển đổi nhanh bên dưới
        sw_rect = pygame.Rect(card.x + 18, btn_submit.bottom + 10, card.width - 36, 24)
        sw_txt = (
            "ĐÃ CÓ TÀI KHOẢN? BẤM ĐỂ ĐĂNG NHẬP >"
            if self.auth_mode == "register"
            else "CHƯA CÓ TÀI KHOẢN? BẤM ĐỂ ĐĂNG KÝ MỚI >"
        )
        sw_surf = self.font_xs.render(sw_txt, False, COLOR_PURPLE_BACK)
        self.screen.blit(sw_surf, (sw_rect.centerx - sw_surf.get_width() // 2, sw_rect.centery - sw_surf.get_height() // 2))
        next_mode = "login" if self.auth_mode == "register" else "register"
        self.auth_click_areas.append((sw_rect.inflate(10, 10), lambda m=next_mode: self._switch_auth_mode(m)))

    def _draw_auth_input_box(self, rect: pygame.Rect, text: str, placeholder: str, focused: bool, is_empty: bool):
        pygame.draw.rect(self.screen, (255, 255, 255), rect, border_radius=8)
        border_col = COLOR_PURPLE_BACK if focused else COLOR_BORDER
        pygame.draw.rect(self.screen, border_col, rect, 3 if focused else 2, border_radius=8)
        if is_empty and not focused:
            t_surf = self.font_sm.render(placeholder, False, (195, 175, 155))
        else:
            t_surf = self.font_sm.render(text[-24:], False, (35, 20, 10))
        self.screen.blit(t_surf, (rect.x + 12, rect.centery - t_surf.get_height() // 2))
        if focused:
            self.screen.blit(self.pointer_img, (rect.x - 18, rect.centery - 9))

    def _set_auth_focus(self, idx: int):
        self.sound.play("click")
        self.auth_focus = idx

    def _toggle_show_pw(self):
        self.sound.play("click")
        self.auth_show_pw = not self.auth_show_pw

    def _handle_auth_keydown(self, event: pygame.event.Event):
        if self.auth_in_progress:
            return
        max_fields = 3 if self.auth_mode == "register" else 2
        if event.key in (pygame.K_TAB, pygame.K_DOWN):
            self.sound.play("click")
            self.auth_focus = (self.auth_focus + 1) % max_fields
            return
        elif event.key == pygame.K_UP:
            self.sound.play("click")
            self.auth_focus = (self.auth_focus - 1) % max_fields
            return
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._submit_auth()
            return
        elif event.key == pygame.K_BACKSPACE:
            self.sound.play("click")
            if self.auth_focus == 0:
                self.auth_username = self.auth_username[:-1]
            elif self.auth_focus == 1:
                self.auth_password = self.auth_password[:-1]
            else:
                self.auth_confirm = self.auth_confirm[:-1]
            return

        ch = event.unicode
        if ch and ch.isprintable() and ch not in ("\r", "\n", "\t"):
            self.sound.play("click")
            if self.auth_focus == 0 and len(self.auth_username) < 20:
                if ch.isalnum() or ch in ("_", "-", "."):
                    self.auth_username += ch
            elif self.auth_focus == 1 and len(self.auth_password) < 24:
                self.auth_password += ch
            elif self.auth_focus == 2 and len(self.auth_confirm) < 24:
                self.auth_confirm += ch

    # =========================================================================
    # XỬ LÝ CLICK CHUỘT & BÀN PHÍM
    # =========================================================================
    def handle_click(self, pos: tuple[int, int]):
        if not self.is_authenticated:
            for rect, cb in self.auth_click_areas:
                if rect.collidepoint(pos):
                    cb()
                    return
            return

        if self.is_admin_mode and self.backend.user_id == "admin" and self.backend.role == "admin":
            if self.admin_modal:
                for rect, cb in self.admin_modal_click_areas:
                    if rect.collidepoint(pos):
                        cb()
                        return
                return
            self.admin_search_focused = False
            for rect, cb in self.admin_click_areas:
                if rect.collidepoint(pos):
                    cb()
                    return
            return

        for rect, cb in self.window_click_areas:
            if rect.collidepoint(pos):
                cb()
                return

        for idx, rect in enumerate(self.shell_btn_rects):
            if rect.collidepoint(pos):
                if idx == 0:
                    self.press_button_a()
                elif idx == 1:
                    self.press_button_b()
                else:
                    self.press_button_c()
                return

        if self.lcd_rect.collidepoint(pos):
            local_pt = (pos[0] - self.lcd_rect.x, pos[1] - self.lcd_rect.y)

            for area_rect, callback in self.clickable_lcd_areas:
                if area_rect.collidepoint(local_pt):
                    callback()
                    return

            if self.menu_state is None and not self.pet.scripted_mode:
                if self.pet.scene == "backyard" and self.pet.has_dig_spot and local_pt[1] > 110:
                    self.press_button_b()
                    return
                if self.pet.scene != "home":
                    self.pet.scene = "home"
                    self.pet.active_npc = None
                    self.sound.play("click")
                    return

                if self.pet.stage == 0:
                    self.pet.egg_timer += 1.5
                    self.sound.play("click")
                    if self.pet.egg_timer >= 5.0:
                        self.pet.hatch()
                        self.show_toast("TRỨNG ĐÃ NỞ RỒI!")
                    else:
                        self.show_toast("TRỨNG ĐANG SẮP NỞ...")
                    return

                cs = STAGE_INFO[self.pet.stage]["size"]
                pet_rect_lcd = pygame.Rect(
                    int(self.pet.x * LCD_SCALE),
                    int(self.pet.y * LCD_SCALE),
                    cs * LCD_SCALE,
                    cs * LCD_SCALE,
                )
                if pet_rect_lcd.collidepoint(local_pt):
                    self.pet.pet_stroke()
                else:
                    self.sound.play("click")
                    self.push_menu("main_grid")

    def handle_keydown(self, key: int):
        if key in (pygame.K_LEFT, pygame.K_a, pygame.K_TAB):
            self.press_button_a()
        elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_b):
            self.press_button_b()
        elif key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_RIGHT, pygame.K_c):
            self.press_button_c()

    async def run(self):
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)
                elif event.type == pygame.MOUSEWHEEL:
                    if self.is_authenticated and self.is_admin_mode and not self.admin_modal:
                        self._change_admin_page(-1 if event.y > 0 else 1)
                elif event.type == pygame.KEYDOWN:
                    if not self.is_authenticated:
                        self._handle_auth_keydown(event)
                    elif self.is_admin_mode and self.backend.user_id == "admin" and self.backend.role == "admin":
                        self._handle_admin_keydown(event)
                    else:
                        self.handle_keydown(event.key)

            self.update(dt)
            self.draw()
            await asyncio.sleep(0)

        pygame.quit()


async def main():
    app = TamawebApp()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
