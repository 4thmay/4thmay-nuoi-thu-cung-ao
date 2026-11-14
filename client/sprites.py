import pygame
import os

_IMAGE_CACHE = {}
_FONT_CACHE = {}

SEASON_PALETTES = {
    "spring": [(99, 160, 75), (99, 160, 75), (127, 208, 96), (150, 242, 113)],
    "summer": [(39, 170, 47), (39, 170, 47), (89, 209, 47), (186, 217, 47)],
    "autumn": [(206, 68, 41), (206, 68, 41), (237, 120, 47), (255, 157, 96)],
    "winter": [(198, 221, 255), (198, 221, 255), (232, 241, 255), (255, 255, 255)],
}
SOURCE_SEASON_COLORS = [
    (192, 22, 178),  # #C016B2
    (192, 23, 178),  # #C017B2
    (239, 28, 222),  # #EF1CDE
    (242, 72, 228),  # #F248E4
]

def get_asset_path(rel_path: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, rel_path)

class VNFontWrapper:
    def __init__(self, font: pygame.font.Font):
        self._font = font

    def render(self, text: str, antialias: bool, color, background=None) -> pygame.Surface:
        if background is not None:
            return self._font.render(str(text), True, color, background)
        return self._font.render(str(text), True, color)

    def size(self, text: str):
        return self._font.size(str(text))

    def get_height(self):
        return self._font.get_height()


def get_pixel_font(size: int = 8):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    # Điều chỉnh cỡ chữ Verdana Bold tương đương độ rộng của PixelColeco
    adj_size = max(8, size - 1)
    font_path = get_asset_path("resources/font/vn_pixel.ttf")
    try:
        if os.path.exists(font_path):
            raw_f = pygame.font.Font(font_path, adj_size)
        else:
            raw_f = pygame.font.SysFont("Verdana", adj_size, bold=True)
    except Exception:
        raw_f = pygame.font.SysFont("Arial", adj_size, bold=True)
    f = VNFontWrapper(raw_f)
    _FONT_CACHE[size] = f
    return f

def load_image(rel_path: str, season: str = None) -> pygame.Surface:
    cache_key = f"{rel_path}::{season}" if season else rel_path
    if cache_key in _IMAGE_CACHE:
        return _IMAGE_CACHE[cache_key]
    
    full_path = get_asset_path(rel_path)
    if not os.path.exists(full_path):
        surf = pygame.Surface((16, 16), pygame.SRCALPHA)
        _IMAGE_CACHE[cache_key] = surf
        return surf
        
    try:
        raw_surf = pygame.image.load(full_path)
        if pygame.display.get_init():
            surf = raw_surf.convert_alpha()
        else:
            surf = raw_surf
            
        if season and season in SEASON_PALETTES:
            surf = surf.copy()
            target_cols = SEASON_PALETTES[season]
            px_array = pygame.PixelArray(surf)
            for src_c, dst_c in zip(SOURCE_SEASON_COLORS, target_cols):
                px_array.replace(src_c, dst_c, distance=0.04)
            del px_array
            
        _IMAGE_CACHE[cache_key] = surf
        return surf
    except Exception as e:
        print(f"Error loading {full_path}: {e}")
        surf = pygame.Surface((16, 16), pygame.SRCALPHA)
        _IMAGE_CACHE[cache_key] = surf
        return surf

class SpriteSheet:
    def __init__(self, rel_path: str, cell_size: int, columns: int = 4, rows: int = 4):
        self.rel_path = rel_path
        self.image = load_image(rel_path)
        self.cell_size = cell_size
        self.columns = columns
        self.rows = rows
        self._frames = []
        self._extract_frames()
        
    def _extract_frames(self):
        img_w, img_h = self.image.get_size()
        for r in range(self.rows):
            for c in range(self.columns):
                x = c * self.cell_size
                y = r * self.cell_size
                frame = pygame.Surface((self.cell_size, self.cell_size), pygame.SRCALPHA)
                if x + self.cell_size <= img_w and y + self.cell_size <= img_h:
                    frame.blit(self.image, (0, 0), pygame.Rect(x, y, self.cell_size, self.cell_size))
                self._frames.append(frame)
                
    def get_frame(self, cell_number: int) -> pygame.Surface:
        if not self._frames:
            return pygame.Surface((self.cell_size, self.cell_size), pygame.SRCALPHA)
        idx = max(0, min(len(self._frames) - 1, cell_number - 1))
        return self._frames[idx]

    def draw_with_breath(self, dest: pygame.Surface, cell_number: int, x: int, y: int, inverted: bool = False, upper_offset_y: int = 0):
        """
        Replicates Drawer.js lines 242-273:
        Splits the sprite into upper 4/5 and lower 1/5 so the upper body bobs (pixelBreath)
        while the feet stay planted on the floor!
        """
        frame = self.get_frame(cell_number)
        if inverted:
            frame = pygame.transform.flip(frame, True, False)
            
        cs = self.cell_size
        upper_h = round((4 / 5) * cs)
        lower_h = cs - upper_h
        
        # Upper 4/5
        dest.blit(frame, (int(x), int(y + upper_offset_y)), pygame.Rect(0, 0, cs, upper_h))
        # Lower 1/5
        dest.blit(frame, (int(x), int(y + upper_h)), pygame.Rect(0, upper_h, cs, lower_h))
