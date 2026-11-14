import asyncio
import datetime
import math
import random
import pygame

from api_client import APIClient
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
        self.lcd_display = pygame.Surface((LCD_DISPLAY, LCD_DISPLAY))

        self.sound = SoundManager()
        self.backend = APIClient("http://127.0.0.1:8000")
        self.pet = Pet(self.sound)

        # Tự động nạp save gần nhất nếu có
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

        # Các nhân vật Mascot Tamaweb trang trí trên màn hình Đăng nhập / Đăng ký
        self.auth_mascots = [
            SpriteSheet("resources/img/character/chara_133b.png", 32, 4, 4),  # Mametchi
            SpriteSheet("resources/img/character/chara_150b.png", 32, 4, 4),  # Lovelitchi
            SpriteSheet("resources/img/character/chara_152b.png", 32, 4, 4),  # Mimitchi
            SpriteSheet("resources/img/character/chara_136b.png", 32, 4, 4),  # Kuchipatchi
        ]
        self.striped_card_hdr = self._create_striped_surface(348, 36, COLOR_STRIPE_A1, COLOR_STRIPE_A2)

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

        self.auth_anim_tick += dt
        if not self.is_authenticated:
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
        self.sound.play("click")
        self.auth_mode = mode
        self.auth_focus = 0
        self.auth_msg = ""

    def _submit_auth(self):
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
            ok, msg = self.backend.register(uname, pwd)
            if not ok:
                self.sound.play("refuse")
                self.auth_msg = msg.upper()
                self.auth_msg_color = COLOR_RED
                return
            # Khởi tạo Pet mới cho tài khoản vừa đăng ký và lưu ngay vào PostgreSQL
            self.pet = Pet(self.sound)
            self.pet.name = uname.upper()[:10]
            self.backend.save_pet(self.pet.to_dict())
            self.sound.play("cheer_success")
            self.is_authenticated = True
            self.menu_state = "welcome_back"
        else:
            ok, msg = self.backend.login(uname, pwd)
            if not ok:
                self.sound.play("refuse")
                self.auth_msg = msg.upper()
                self.auth_msg_color = COLOR_RED
                return
            # Tải dữ liệu Pet của tài khoản từ PostgreSQL
            self.pet = Pet(self.sound)
            saved_data = self.backend.load_pet()
            if saved_data:
                self.pet.load_from_dict(saved_data)
            else:
                self.pet.name = uname.upper()[:10]
                self.backend.save_pet(self.pet.to_dict())
            self.sound.play("cheer_success")
            self.is_authenticated = True
            self.menu_state = "welcome_back"

    def _logout_account(self):
        self.sound.play("click")
        self.backend.save_pet(self.pet.to_dict())
        self.close_all_menus()
        self.is_authenticated = False
        self.auth_password = ""
        self.auth_confirm = ""
        self.auth_focus = 0
        self.auth_msg = ""

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
        sub_col = COLOR_GREEN if self.auth_mode == "register" else COLOR_TEXT_ORANGE
        sub_shadow = (45, 145, 30) if self.auth_mode == "register" else (190, 85, 0)
        pygame.draw.rect(self.screen, sub_shadow, btn_submit.move(0, 4), border_radius=12)
        pygame.draw.rect(self.screen, sub_col, btn_submit, border_radius=12)
        pygame.draw.rect(self.screen, (255, 255, 255), btn_submit, 2, border_radius=12)
        sub_label = "ĐĂNG KÝ & VÀO GAME" if self.auth_mode == "register" else "ĐĂNG NHẬP VÀO GAME"
        sub_surf = self.font_md.render(sub_label, False, (255, 255, 255))
        self.screen.blit(sub_surf, (btn_submit.centerx - sub_surf.get_width() // 2, btn_submit.centery - sub_surf.get_height() // 2))
        self.auth_click_areas.append((btn_submit, self._submit_auth))

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
        self.auth_click_areas.append((sw_rect, lambda m=next_mode: self._switch_auth_mode(m)))

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
                elif event.type == pygame.KEYDOWN:
                    if not self.is_authenticated:
                        self._handle_auth_keydown(event)
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
