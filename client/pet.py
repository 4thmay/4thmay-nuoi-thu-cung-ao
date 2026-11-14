import math
import random
import pygame
from definitions import (
    ACCESSORIES,
    ANIMAL_CHARACTERS,
    FOODS,
    FURNITURES,
    ITEMS,
    NPC_CHARACTERS,
    PLANTS,
    ROOM_BACKGROUNDS,
    STAGE_CHARACTERS,
)
from sprites import SpriteSheet, load_image

STAGE_INFO = [
    {"name": "TRỨNG", "size": 16, "cols": 2, "rows": 1, "offset_y": 8},
    {"name": "SƠ SINH", "size": 16, "cols": 4, "rows": 4, "offset_y": 8},
    {"name": "THIẾU NHI", "size": 24, "cols": 4, "rows": 4, "offset_y": 4},
    {"name": "THIẾU NIÊN", "size": 24, "cols": 4, "rows": 4, "offset_y": 4},
    {"name": "TRƯỞNG THÀNH", "size": 32, "cols": 4, "rows": 4, "offset_y": 0},
    {"name": "CAO NIÊN", "size": 32, "cols": 4, "rows": 4, "offset_y": 0},
]

# Chuẩn PetDefinition.js (lines 13-231)
ANIMATIONS = {
    "idle": {"frames": [1], "frame_time": 0.5},
    "idle_side": {"frames": [9], "frame_time": 0.5},
    "idle_uncomfortable": {"frames": [4], "frame_time": 0.5},
    "moving": {"frames": [10, 11], "frame_time": 0.12},
    "sitting": {"frames": [14], "frame_time": 0.3},
    "eating": {"frames": [14, 15], "frame_time": 0.25},
    "open_mouth": {"frames": [15], "frame_time": 0.25},
    "cheering": {"frames": [2, 3], "frame_time": 0.25},
    "uncomfortable": {"frames": [4, 5], "frame_time": 0.4},
    "angry": {"frames": [6], "frame_time": 0.4},
    "shocked": {"frames": [7], "frame_time": 0.25},
    "blush": {"frames": [8], "frame_time": 0.3},
    "refuse": {"frames": [4, 5, 6], "frame_time": 0.3},
    "sleeping": {"frames": [16], "frame_time": 1.0},
    "jumping": {"frames": [2], "frame_time": 0.25},
}

POOP_POSITIONS = [
    (68, 72),
    (78, 78),
    (16, 74),
    (8, 78),
]

FURNITURE_SLOTS = [
    (10, 48),
    (64, 48),
    (18, 60),
    (56, 60),
]

GARDEN_PATCH_POSITIONS = [
    (12, 56),
    (34, 56),
    (56, 56),
    (76, 56),
]


class Pet:
    def __init__(self, sound_mgr=None):
        self.sound = sound_mgr
        self.name = "TAMAGOTCHI"
        self.stage = 1  # 0: Egg, 1: Baby, 2: Child, 3: Teen, 4: Adult, 5: Elder
        self.generation = 1
        self.gender = random.choice(["BÉ TRAI", "BÉ GÁI"])
        self.char_idx = 0
        self.character_file = STAGE_CHARACTERS[1][0]
        self.level = 1
        self.exp = 0
        self.gold = 350

        # Chỉ số chuẩn PetDefinition.js (0 - 100)
        self.hunger = 80.0
        self.energy = 85.0     # sleep
        self.hygiene = 90.0    # cleanliness
        self.happiness = 80.0  # fun
        self.health = 95.0
        self.bladder = 80.0
        self.discipline = 75.0

        # 3 Kỹ năng trường học chuẩn Tamaweb (Expression, Logic, Endurance)
        self.skill_expression = 10.0
        self.skill_logic = 10.0
        self.skill_endurance = 10.0

        self.age_seconds = 0.0
        self.is_sleeping = False
        self.is_sick = False
        self.has_toothache = False
        self.is_misbehaving = False
        self.poop_count = 0

        # Cảnh & Căn phòng hiện tại
        self.scene = "home"
        self.room_bg = "resources/img/background/house/02.png"
        self.kitchen_bg = "resources/img/background/house/kitchen_03.png"
        self.bathroom_bg = "resources/img/background/house/bathroom_01.png"

        # Túi đồ & Bộ sưu tập chuẩn Tamaweb
        self.equipped_accessories = []  # list of accessory ids (e.g. ["crown"])
        self.owned_accessories = ["crown", "witch hat", "wings"]
        self.placed_furniture = []      # list of furniture ids (max 4)
        self.owned_furniture = ["sofa_blue", "stand_blue", "plant_01"]
        self.inventory_harvest = {"red tulip": 2, "blue tulip": 2, "green tulip": 2, "bamboo": 2}
        self.unlocked_characters = [self.character_file]

        # Vườn cây (Garden: 4 ô đất trồng cây từ plants.png)
        self.garden_plots = [
            {"plant_id": "tomato", "sprite": 33, "stage": 2, "watered": True, "timer": 0.0},
            {"plant_id": "purple tulip", "sprite": 1, "stage": 3, "watered": True, "timer": 0.0},
            None,
            None,
        ]

        # Sân sau (Backyard: bát thức ăn dụ thú cưng mèo/chó)
        self.bowl_has_treat = True
        self.has_dig_spot = True
        self.backyard_animal = {
            "sprite": ANIMAL_CHARACTERS[0],
            "x": 22.0,
            "y": 64.0,
            "target_x": 60.0,
            "inverted": True,
        }

        # Danh sách bạn bè & Gia phả (Friends & Family Tree)
        self.friends = [
            {"name": "MAMETCHI", "sprite": "resources/img/character/chara_133b.png", "affection": 65},
            {"name": "KUCHIPATCHI", "sprite": "resources/img/character/chara_136b.png", "affection": 50},
            {"name": "MEMETCHI", "sprite": "resources/img/character/chara_140b.png", "affection": 45},
            {"name": "LOVELITCHI", "sprite": "resources/img/character/chara_150b.png", "affection": 80},
        ]
        self.family_history = []  # Lưu các thế hệ trước
        self.active_npc = None    # NPC xuất hiện cùng trong cảnh (Park, Restaurant, Clinic, School, Fortune, Wedding)

        # Nhiệm vụ hàng ngày (Missions.js)
        self.missions = [
            {"id": "feed", "title": "ĂN 2 BỮA", "progress": 0, "goal": 2, "reward": 50, "claimed": False},
            {"id": "bath", "title": "TẮM RỬA SẠCH", "progress": 0, "goal": 1, "reward": 40, "claimed": False},
            {"id": "play", "title": "CHƠI ĐỒ CHƠI", "progress": 0, "goal": 1, "reward": 60, "claimed": False},
            {"id": "park", "title": "ĐI DẠO PHỐ", "progress": 0, "goal": 1, "reward": 45, "claimed": False},
            {"id": "water", "title": "TƯỚI CÂY", "progress": 0, "goal": 1, "reward": 55, "claimed": False},
        ]

        # Mong muốn hiện tại của Pet (Current Want)
        self.current_want = {"type": "food", "name": "BÁNH PIZZA", "sprite": 515}

        # Toạ độ pet trên màn hình 96x96
        self.x = 36.0
        self.y = 52.0
        self.target_x = None
        self.inverted = False
        self.wander_timer = 2.0

        # Animation state
        self.state = "idle"
        self.anim_idx = 0
        self.anim_timer = 0.0
        self.breath_timer = 0.0
        self.upper_offset_y = 0

        # Scripted Activity State
        self.scripted_mode = None
        self.scripted_timer = 0.0
        self.active_food_sprite = 2
        self.active_food_bite = 0
        self.active_item_sprite = 1
        self.mop_x = -96.0
        self.foam_bubbles = []
        self.thought_timer = 0.0

        # Floating particles
        self.particles = []
        self.sleep_z_timer = 0.0
        self.flip_tick = 0.0

        self.spritesheet = None
        self._load_stage_sprite()

        # Preload Spritesheets & Misc Sprites từ Tamaweb
        self.foods_sheet = SpriteSheet("resources/img/item/foods_on.png", 24, 33, 33)
        self.items_sheet = SpriteSheet("resources/img/item/items.png", 22, 10, 10)
        self.plants_sheet = SpriteSheet("resources/img/item/plants.png", 24, 28, 28)
        self.poop_img = load_image("resources/img/misc/poop.png")
        self.shadow_img = load_image("resources/img/misc/shadow_01.png")
        self.sleep_z_img = load_image("resources/img/misc/sleep_z_01.png")
        self.happy_icon = load_image("resources/img/misc/happy_icon.png")
        self.exclaim_icon = load_image("resources/img/misc/thought_exclaim.png")
        self.heart1_img = load_image("resources/img/misc/heart_particle_01.png")
        self.heart2_img = load_image("resources/img/misc/heart_particle_02.png")
        self.arrow_up_img = load_image("resources/img/misc/arrow_up_green_01.png")
        self.stinky_img = load_image("resources/img/misc/stinky_01.png")
        self.needstoilet_img = load_image("resources/img/misc/needstoilet_01.png")
        self.sickness_img = load_image("resources/img/misc/sickness_overlay_01.png")
        self.toothache_img = load_image("resources/img/misc/toothache_01.png")
        self.toothbrush_img = load_image("resources/img/misc/toothbrush_01.png")
        self.foam_single_img = load_image("resources/img/misc/foam_single.png")
        self.grime_img = load_image("resources/img/misc/interior_grime_01.png")
        self.cleaner_img = pygame.transform.rotate(load_image("resources/img/misc/cleaner.png"), -90)
        self.dark_overlay = load_image("resources/img/background/house/dark_overlay.png")
        self.doctor_sheet = SpriteSheet("resources/img/character/doctor_01.png", 32, 4, 4)
        self.thought_bubble_img = load_image("resources/img/misc/thought_bubble_01.png")
        self.thought_talk_img = load_image("resources/img/misc/thought_talk.png")
        self.thought_like_img = load_image("resources/img/misc/thought_like.png")
        self.pet_bowl_img = load_image("resources/img/misc/pet_bowl_01.png")
        self.dig_spot_sheet = SpriteSheet("resources/img/misc/dig_spot_01.png", 24, 1, 2)
        self.grass_layer_img = load_image("resources/img/misc/grass_layer_01.png", season="spring")
        self.tree_img = load_image("resources/img/misc/tree_01.png", season="spring")
        self.garden_patch_dry = load_image("resources/img/misc/garden_patch_01.png")
        self.garden_patch_wet = load_image("resources/img/misc/garden_patch_01_wet.png")
        self.watering_can_img = load_image("resources/img/misc/watering_can_01.png")
        self.wedding_overlay_img = load_image("resources/img/background/house/wedding_overlay.png")

    def _load_stage_sprite(self):
        info = STAGE_INFO[self.stage]
        chars = STAGE_CHARACTERS.get(self.stage, STAGE_CHARACTERS[1])
        self.char_idx = self.char_idx % len(chars)
        self.character_file = chars[self.char_idx]
        if self.character_file not in self.unlocked_characters:
            self.unlocked_characters.append(self.character_file)
        self.spritesheet = SpriteSheet(self.character_file, info["size"], info["cols"], info["rows"])
        self.offset_y = info["offset_y"]
        self.y = 96 - info["size"] - 10 + self.offset_y

    def advance_mission(self, mission_id: str):
        for m in self.missions:
            if m["id"] == mission_id and not m["claimed"]:
                m["progress"] = min(m["goal"], m["progress"] + 1)

    def set_state(self, new_state: str):
        if self.state != new_state:
            self.state = new_state
            self.anim_idx = 0
            self.anim_timer = 0.0

    def spawn_hearts(self, count: int = 3):
        cs = STAGE_INFO[self.stage]["size"]
        for _ in range(count):
            self.particles.append({
                "type": "heart",
                "img": random.choice([self.heart1_img, self.heart2_img]),
                "x": self.x + random.uniform(0, cs - 8),
                "y": self.y - 4,
                "vy": -14.0,
                "vx": random.uniform(-6.0, 6.0),
                "life": 1.2,
            })

    def spawn_arrows(self, count: int = 4):
        cs = STAGE_INFO[self.stage]["size"]
        for i in range(count):
            self.particles.append({
                "type": "arrow",
                "img": self.arrow_up_img,
                "x": self.x + random.uniform(-4, cs),
                "y": self.y + random.uniform(0, cs // 2),
                "vy": -18.0,
                "vx": 0.0,
                "life": 1.0 + i * 0.15,
            })

    def update(self, dt: float):
        self.age_seconds += dt
        self.flip_tick += dt

        if self.thought_timer > 0:
            self.thought_timer = max(0.0, self.thought_timer - dt)

        # Cập nhật cây trồng trong Garden
        for plot in self.garden_plots:
            if plot and plot["watered"] and plot["stage"] < 3:
                plot["timer"] += dt
                if plot["timer"] >= 20.0:
                    plot["timer"] = 0.0
                    plot["stage"] += 1

        # Cập nhật thú cưng hoang dã ở Backyard
        if self.backyard_animal and self.scene == "backyard":
            ax = self.backyard_animal["x"]
            tx = self.backyard_animal["target_x"]
            if abs(ax - tx) <= 12.0 * dt:
                self.backyard_animal["target_x"] = float(random.randint(12, 72))
            elif ax < tx:
                self.backyard_animal["x"] += 12.0 * dt
                self.backyard_animal["inverted"] = True
            else:
                self.backyard_animal["x"] -= 12.0 * dt
                self.backyard_animal["inverted"] = False

        # PixelBreath (Object2d.animations.pixelBreath)
        self.breath_timer += dt
        if self.breath_timer >= 0.55:
            self.breath_timer = 0.0
            self.upper_offset_y = 1 if self.upper_offset_y == 0 else 0

        # Cập nhật particles
        alive_particles = []
        for p in self.particles:
            p["life"] -= dt
            if p["life"] > 0:
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
                alive_particles.append(p)
        self.particles = alive_particles

        # Xử lý các hoạt cảnh đặc biệt
        if self.scripted_mode:
            self.scripted_timer += dt
            self._update_scripted_mode(dt)
            self._update_animation_frames(dt)
            return

        if self.is_sleeping:
            self.energy = min(100.0, self.energy + dt * 4.5)
            self.hunger = max(0.0, self.hunger - dt * 0.2)
            self.set_state("sleeping")
            self.sleep_z_timer += dt
            if self.sleep_z_timer >= 0.85:
                self.sleep_z_timer = 0.0
                self.particles.append({
                    "type": "z",
                    "img": self.sleep_z_img,
                    "x": self.x + STAGE_INFO[self.stage]["size"] * 0.5,
                    "y": self.y - 6,
                    "vy": -10.0,
                    "vx": random.choice([-4.0, 4.0]),
                    "life": 1.4,
                })
            self._update_animation_frames(dt)
            return

        # Giảm chỉ số tự nhiên khi thức
        self.energy = max(0.0, self.energy - dt * 0.2)
        self.hunger = max(0.0, self.hunger - dt * 0.35)
        self.hygiene = max(0.0, self.hygiene - dt * 0.2)
        self.happiness = max(0.0, self.happiness - dt * 0.3)
        self.bladder = max(0.0, self.bladder - dt * 0.35)

        if self.bladder <= 0.0:
            self.bladder = 100.0
            if self.poop_count < 4:
                self.poop_count += 1
                self.hygiene = max(0.0, self.hygiene - 15.0)
                if self.sound:
                    self.sound.play("sad")

        if self.poop_count >= 2 or self.hygiene < 20 or self.hunger < 15:
            self.health = max(0.0, self.health - dt * 0.4)
            if self.health < 45:
                self.is_sick = True

        # Wander đi lại ngẫu nhiên trong phòng
        cs = STAGE_INFO[self.stage]["size"]
        if self.scene == "garden":
            self.y = 48 - cs + self.offset_y
        else:
            self.y = 96 - cs - 10 + self.offset_y

        if self.target_x is not None:
            speed = 18.0 * dt
            if abs(self.x - self.target_x) <= speed:
                self.x = float(self.target_x)
                self.target_x = None
                if self.hunger < 30 or self.happiness < 30 or self.is_sick:
                    self.set_state("idle_uncomfortable")
                else:
                    self.set_state("idle")
            else:
                self.set_state("moving")
                if self.x < self.target_x:
                    self.x += speed
                    self.inverted = True
                else:
                    self.x -= speed
                    self.inverted = False
        else:
            self.wander_timer -= dt
            if self.wander_timer <= 0:
                self.wander_timer = random.uniform(2.5, 5.5)
                if random.random() < 0.7:
                    self.target_x = random.randint(8, max(12, 96 - cs - 8))
                else:
                    self.set_state(random.choice(["idle", "idle_side", "sitting"]))

        self._update_animation_frames(dt)
        self._check_evolution()

    def _update_animation_frames(self, dt: float):
        if self.stage == 0:
            return
        anim = ANIMATIONS.get(self.state, ANIMATIONS["idle"])
        frames = anim["frames"]
        self.anim_timer += dt
        if self.anim_timer >= anim["frame_time"]:
            self.anim_timer = 0.0
            self.anim_idx = (self.anim_idx + 1) % len(frames)

    def _update_scripted_mode(self, dt: float):
        cs = STAGE_INFO[self.stage]["size"]
        if self.scripted_mode == "feeding":
            self.scene = "kitchen"
            self.x = 58 - cs // 2
            self.y = 66 - cs + self.offset_y
            self.inverted = False
            if self.scripted_timer < 3.2:
                self.set_state("eating")
                bite = min(2, int(self.scripted_timer / 1.05))
                if bite != self.active_food_bite:
                    self.active_food_bite = bite
                    if self.sound:
                        self.sound.play("eat")
            elif self.scripted_timer < 4.4:
                if self.state != "cheering":
                    self.set_state("cheering")
                    if self.sound:
                        self.sound.play("cheer_success")
            else:
                self.scripted_mode = None
                self.scene = "home"
                self.x = 48 - cs // 2
                self.set_state("idle")

        elif self.scripted_mode == "playing_item":
            self.scene = "home"
            self.x = 34 - cs // 2
            self.y = 96 - cs - 10 + self.offset_y
            self.inverted = True
            self.set_state("cheering" if int(self.scripted_timer * 2) % 2 == 0 else "jumping")
            if self.scripted_timer >= 3.5:
                self.scripted_mode = None
                self.x = 48 - cs // 2
                self.set_state("idle")

        elif self.scripted_mode == "bathing":
            # Chuẩn Activities.bathe() (lines 4474-4542): đứng ở (64%, 64%) trong bồn tắm + bọt foam_single.png
            self.scene = "bathroom"
            self.x = 61 - cs // 2
            self.y = 61 - cs + self.offset_y
            self.inverted = (int(self.scripted_timer * 2.5) % 2 == 0)
            self.set_state("cheering" if self.scripted_timer > 2.4 else "idle")
            if self.scripted_timer >= 4.0:
                self.hygiene = 100.0
                self.foam_bubbles.clear()
                self.scripted_mode = None
                self.scene = "home"
                self.x = 48 - cs // 2
                self.set_state("cheering")
                if self.sound:
                    self.sound.play("cheer_success")

        elif self.scripted_mode == "cleaning":
            self.scene = "home"
            self.mop_x += 95.0 * dt
            if self.x < self.mop_x + 70:
                self.x = min(76, self.mop_x + 70)
                self.set_state("shocked")
            if self.mop_x >= 64:
                self.poop_count = 0
                self.hygiene = min(100.0, self.hygiene + 40.0)
                self.scripted_mode = None
                self.x = 48 - cs // 2
                self.set_state("cheering")
                if self.sound:
                    self.sound.play("cheer_success")

        elif self.scripted_mode == "toilet":
            self.scene = "bathroom"
            self.x = 20 - cs // 2
            self.y = 81 - cs + self.offset_y
            self.inverted = True
            self.set_state("sitting" if self.scripted_timer < 2.0 else "cheering")
            if self.scripted_timer >= 3.2:
                self.bladder = 100.0
                self.poop_count = 0
                self.scripted_mode = None
                self.scene = "home"
                self.x = 48 - cs // 2
                self.set_state("idle")

        elif self.scripted_mode == "brushing":
            self.scene = "bathroom"
            self.x = 48 - cs // 2
            self.y = 78 - cs + self.offset_y
            self.set_state("open_mouth")
            if self.scripted_timer >= 3.0:
                self.has_toothache = False
                self.hygiene = min(100.0, self.hygiene + 20.0)
                self.scripted_mode = None
                self.scene = "home"
                self.set_state("cheering")
                if self.sound:
                    self.sound.play("cheer_success")

        elif self.scripted_mode == "clinic":
            self.scene = "clinic"
            self.x = 62 - cs // 2
            self.y = 78 - cs + self.offset_y
            self.inverted = False
            self.set_state("shocked" if self.scripted_timer < 1.5 else "cheering")
            if self.scripted_timer >= 3.2:
                self.is_sick = False
                self.has_toothache = False
                self.health = 100.0
                self.scripted_mode = None
                self.scene = "home"
                self.x = 48 - cs // 2
                self.set_state("idle")

        elif self.scripted_mode == "wedding":
            self.scene = "wedding"
            self.x = 34 - cs // 2
            self.y = 82 - cs + self.offset_y
            self.inverted = True
            self.set_state("blush" if self.scripted_timer < 2.2 else "cheering")
            if self.scripted_timer >= 4.2:
                # Sinh thế hệ mới (Next Gen Baby) và lưu gia phả!
                partner = self.active_npc or self.friends[0]
                self.family_history.append({
                    "gen": self.generation,
                    "name": self.name,
                    "sprite": self.character_file,
                    "partner_name": partner["name"],
                    "partner_sprite": partner["sprite"],
                })
                self.generation += 1
                self.stage = 1
                self.char_idx = random.randint(0, len(STAGE_CHARACTERS[1]) - 1)
                self._load_stage_sprite()
                self.scripted_mode = None
                self.active_npc = None
                self.scene = "home"
                self.x = 48 - STAGE_INFO[1]["size"] // 2
                self.spawn_hearts(6)
                if self.sound:
                    self.sound.play("hatch")

        elif self.scripted_mode in ("praising", "petting", "scolding"):
            if self.scripted_timer >= 2.2:
                self.scripted_mode = None
                self.set_state("idle")

    def _check_evolution(self):
        thresholds = [0, 80, 200, 400, 700]
        if 0 < self.stage < len(STAGE_INFO) - 1:
            if self.exp >= thresholds[self.stage]:
                self.evolve_next()

    def evolve_next(self):
        self.stage = (self.stage % (len(STAGE_INFO) - 1)) + 1
        self.level += 1
        self.char_idx = random.randint(0, len(STAGE_CHARACTERS[self.stage]) - 1)
        self._load_stage_sprite()
        self.spawn_arrows(6)
        self.spawn_hearts(4)
        if self.sound:
            self.sound.play("hatch")

    def change_character_variant(self):
        chars = STAGE_CHARACTERS[self.stage]
        self.char_idx = (self.char_idx + 1) % len(chars)
        self._load_stage_sprite()
        if self.sound:
            self.sound.play("click")

    def start_feed(self, food_def: dict, free_override: bool = False) -> tuple[bool, str]:
        if self.is_sleeping:
            if self.sound:
                self.sound.play("refuse")
            return False, "BÉ ĐANG NGỦ!"
        price = 0 if free_override else food_def.get("price", 0)
        if self.gold < price:
            if self.sound:
                self.sound.play("refuse")
            return False, "KHÔNG ĐỦ TIỀN!"
        self.gold -= price
        self.hunger = min(100.0, self.hunger + food_def.get("hunger", 20))
        self.happiness = min(100.0, self.happiness + food_def.get("fun", 5))
        self.health = max(0.0, min(100.0, self.health + food_def.get("health", 0)))
        self.exp += 12
        self.advance_mission("feed")
        if food_def.get("type") == "treat" and random.random() < 0.2:
            self.has_toothache = True

        # Kiểm tra nếu trúng món pet đang thèm (current_want)
        if self.current_want and self.current_want.get("name") == food_def["name"]:
            self.happiness = 100.0
            self.gold += 25
            self._roll_new_want()

        self.active_food_sprite = food_def["sprite"]
        self.active_food_bite = 0
        self.scripted_mode = "feeding"
        self.scripted_timer = 0.0
        self.target_x = None
        if self.sound:
            self.sound.play("eat")
        return True, f"ĐÃ ĂN {food_def['name']}!"

    def start_play_item(self, item_def: dict) -> tuple[bool, str]:
        if self.is_sleeping:
            return False, "BÉ ĐANG NGỦ!"
        self.happiness = min(100.0, self.happiness + item_def.get("fun", 15))
        self.skill_logic = min(100.0, self.skill_logic + item_def.get("logic", 0.5) * 4)
        self.skill_expression = min(100.0, self.skill_expression + item_def.get("expression", 0.5) * 4)
        self.skill_endurance = min(100.0, self.skill_endurance + item_def.get("endurance", 0.5) * 4)
        self.exp += 15
        self.advance_mission("play")
        self.active_item_sprite = item_def["sprite"]
        self.scripted_mode = "playing_item"
        self.scripted_timer = 0.0
        self.target_x = None
        self.spawn_hearts(3)
        if self.sound:
            self.sound.play("cheer")
        return True, f"ĐÃ CHƠI {item_def['name']}!"

    def _roll_new_want(self):
        if random.random() < 0.6:
            f = random.choice(FOODS[:25])
            self.current_want = {"type": "food", "name": f["name"], "sprite": f["sprite"]}
        else:
            it = random.choice(ITEMS)
            self.current_want = {"type": "item", "name": it["name"], "sprite": it["sprite"]}

    def show_current_want(self):
        self.thought_timer = 4.0
        if self.sound:
            self.sound.play("click")

    def start_bath(self):
        if self.is_sleeping:
            return
        self.scripted_mode = "bathing"
        self.scripted_timer = 0.0
        self.target_x = None
        self.exp += 10
        self.advance_mission("bath")
        # Tạo 12 hạt bọt xà phòng foam_single.png quanh bồn tắm giống Activities.bathe()
        self.foam_bubbles = [
            {
                "x": 50 + random.uniform(-14, 14),
                "y": 42 + random.uniform(-3, 4),
                "phase": random.uniform(0, 6.28),
            }
            for _ in range(12)
        ]
        if self.sound:
            self.sound.play("clean")

    def start_clean_room(self):
        if self.is_sleeping:
            return
        self.scripted_mode = "cleaning"
        self.scripted_timer = 0.0
        self.mop_x = -96.0
        self.target_x = None
        self.exp += 10
        if self.sound:
            self.sound.play("clean")

    def start_toilet(self):
        if self.is_sleeping:
            return
        self.scripted_mode = "toilet"
        self.scripted_timer = 0.0
        self.target_x = None
        self.exp += 8
        if self.sound:
            self.sound.play("click")

    def start_brush_teeth(self):
        if self.is_sleeping:
            return
        self.scripted_mode = "brushing"
        self.scripted_timer = 0.0
        self.target_x = None
        self.exp += 8
        if self.sound:
            self.sound.play("clean")

    def start_clinic(self):
        self.scripted_mode = "clinic"
        self.scripted_timer = 0.0
        self.target_x = None
        self.exp += 15
        if self.sound:
            self.sound.play("complete")

    def start_wedding(self, friend_def: dict):
        self.active_npc = friend_def
        self.scripted_mode = "wedding"
        self.scripted_timer = 0.0
        self.target_x = None
        self.spawn_hearts(6)
        if self.sound:
            self.sound.play("cheer_success")

    def praise(self):
        if self.is_sleeping:
            return
        self.discipline = min(100.0, self.discipline + 10.0)
        self.happiness = min(100.0, self.happiness + 15.0)
        self.is_misbehaving = False
        self.exp += 10
        self.scripted_mode = "praising"
        self.scripted_timer = 0.0
        self.set_state("cheering")
        self.spawn_arrows(5)
        if self.sound:
            self.sound.play("cheer_success")

    def pet_stroke(self):
        if self.is_sleeping:
            return
        self.happiness = min(100.0, self.happiness + 15.0)
        self.exp += 8
        self.scripted_mode = "petting"
        self.scripted_timer = 0.0
        self.set_state("blush")
        self.spawn_hearts(4)
        if self.sound:
            self.sound.play("blush")

    def scold(self):
        if self.is_sleeping:
            return
        self.discipline = min(100.0, self.discipline + 15.0)
        self.happiness = max(0.0, self.happiness - 10.0)
        self.is_misbehaving = False
        self.scripted_mode = "scolding"
        self.scripted_timer = 0.0
        self.set_state("uncomfortable")
        if self.sound:
            self.sound.play("sad")

    def toggle_sleep(self) -> bool:
        self.is_sleeping = not self.is_sleeping
        self.target_x = None
        if self.is_sleeping:
            cs = STAGE_INFO[self.stage]["size"]
            self.x = 48 - cs // 2
            self.set_state("sleeping")
        else:
            self.set_state("idle")
        return self.is_sleeping

    def toggle_accessory(self, acc_id: str) -> bool:
        if acc_id in self.equipped_accessories:
            self.equipped_accessories.remove(acc_id)
            return False
        else:
            if len(self.equipped_accessories) >= 2:
                self.equipped_accessories.pop(0)
            self.equipped_accessories.append(acc_id)
            return True

    def toggle_furniture(self, furn_id: str) -> bool:
        if furn_id in self.placed_furniture:
            self.placed_furniture.remove(furn_id)
            return False
        else:
            if len(self.placed_furniture) >= 4:
                self.placed_furniture.pop(0)
            self.placed_furniture.append(furn_id)
            return True

    def _draw_accessories(self, lcd: pygame.Surface, front_layer: bool, breath_y: int):
        cs = STAGE_INFO[self.stage]["size"]
        for acc_id in self.equipped_accessories:
            acc_def = next((a for a in ACCESSORIES if a["id"] == acc_id), None)
            if not acc_def or acc_def["front"] != front_layer:
                continue
            acc_img = load_image(acc_def["image"])
            if self.inverted:
                acc_img = pygame.transform.flip(acc_img, True, False)
            ax = int(self.x + (cs - acc_img.get_width()) // 2)
            ay = int(self.y - (acc_img.get_height() - cs) // 2 - (4 if cs <= 16 else 2) - breath_y)
            lcd.blit(acc_img, (ax, ay))

    def draw(self, lcd: pygame.Surface):
        cs = STAGE_INFO[self.stage]["size"]
        anim = ANIMATIONS.get(self.state, ANIMATIONS["idle"])
        frames = anim["frames"]
        cell_num = frames[self.anim_idx % len(frames)]

        # 0. Vẽ nội thất trong phòng khách (Furniture), vườn cây (Garden), hoặc sân sau (Backyard)
        if self.scene == "home":
            for i, fid in enumerate(self.placed_furniture[:4]):
                fdef = next((f for f in FURNITURES if f["id"] == fid), None)
                if fdef:
                    fimg = load_image(fdef["image"])
                    fx, fy = FURNITURE_SLOTS[i % len(FURNITURE_SLOTS)]
                    lcd.blit(fimg, (fx, fy))
            if self.poop_count >= 2:
                lcd.blit(self.grime_img, (0, 0))

        elif self.scene == "backyard":
            lcd.blit(self.tree_img, (8, 10))
            lcd.blit(self.tree_img, (56, 12))
            lcd.blit(self.grass_layer_img, (0, 66))
            lcd.blit(self.pet_bowl_img, (14, 62))
            if self.bowl_has_treat:
                treat_surf = self.foods_sheet.get_frame(881)
                lcd.blit(treat_surf, (13, 56))
            if self.has_dig_spot:
                dig_frame = self.dig_spot_sheet.get_frame(1 if int(self.flip_tick * 2) % 2 == 0 else 2)
                lcd.blit(dig_frame, (68, 72))
            if self.backyard_animal:
                ani_sheet = SpriteSheet(self.backyard_animal["sprite"], 24, 4, 4)
                ani_cell = 10 if int(self.flip_tick * 6) % 2 == 0 else 11
                ani_sheet.draw_with_breath(
                    lcd, ani_cell, int(self.backyard_animal["x"]), int(self.backyard_animal["y"]),
                    inverted=self.backyard_animal["inverted"], upper_offset_y=self.upper_offset_y
                )

        elif self.scene == "garden":
            for idx, (gx, gy) in enumerate(GARDEN_PATCH_POSITIONS):
                plot = self.garden_plots[idx] if idx < len(self.garden_plots) else None
                patch_img = self.garden_patch_wet if (plot and plot["watered"]) else self.garden_patch_dry
                lcd.blit(patch_img, (gx - 8, gy))
                if plot:
                    p_cell = plot["sprite"] + min(3, plot["stage"])
                    p_surf = self.plants_sheet.get_frame(p_cell)
                    lcd.blit(p_surf, (gx - 8, gy - 12))

        # 1. Vẽ bóng dưới chân pet (shadow_01.png)
        if self.scene not in ("kitchen", "bathroom", "wedding") and not self.is_sleeping:
            scaled_shadow = pygame.transform.scale(self.shadow_img, (cs, cs))
            sh_y = int(self.y + math.ceil(cs / 2.1))
            lcd.blit(scaled_shadow, (int(self.x), sh_y))

        # 2. Vẽ phân trên sàn (poop.png) ở phòng khách
        if self.scene == "home":
            flip_poop = (int(self.flip_tick * 3) % 2 == 1)
            for i in range(self.poop_count):
                px, py = POOP_POSITIONS[i % len(POOP_POSITIONS)]
                if self.scripted_mode == "cleaning" and px < self.mop_x + 75:
                    px = int(self.mop_x + 75)
                p_img = pygame.transform.flip(self.poop_img, flip_poop, False)
                lcd.blit(p_img, (px, py))

        # 3. Vẽ Bác sĩ hoặc NPC bạn bè (Park, Restaurant, Fortune Teller, School, Wedding)
        if self.scene == "clinic":
            doc_frame = 2 if (int(self.flip_tick * 4) % 2 == 0) else 1
            self.doctor_sheet.draw_with_breath(lcd, doc_frame, 14, 46, inverted=True, upper_offset_y=self.upper_offset_y)
        elif self.active_npc and self.scene in ("park", "restaurant", "fortune", "school", "parents", "wedding"):
            npc_sprite = self.active_npc.get("sprite", NPC_CHARACTERS[0])
            npc_sheet = SpriteSheet(npc_sprite, 32, 4, 4)
            nx = 58 if self.scene != "fortune" else 62
            ny = 50 if self.scene == "wedding" else 54
            npc_sheet.draw_with_breath(lcd, 1, nx, ny, inverted=False, upper_offset_y=self.upper_offset_y)
            if int(self.flip_tick * 2) % 2 == 0:
                lcd.blit(self.thought_talk_img, (nx + 8, ny - 12))

        # 4. Vẽ phụ kiện lớp sau (Wings / Cloof) + Nhân vật Pet + Phụ kiện lớp trước (Hats / Crowns)
        breath_y = self.upper_offset_y if self.state in ("idle", "idle_side", "sitting") else 0
        if not self.is_sleeping:
            self._draw_accessories(lcd, front_layer=False, breath_y=breath_y)

        self.spritesheet.draw_with_breath(
            lcd,
            cell_num,
            int(self.x),
            int(self.y),
            inverted=self.inverted,
            upper_offset_y=breath_y,
        )

        if not self.is_sleeping:
            self._draw_accessories(lcd, front_layer=True, breath_y=breath_y)

        # 5. Nếu đang tắm: cắt mặt trước bồn tắm [38, 51]..[81, 68] đè lên người pet + vẽ bọt xà phòng foam_single.png
        if self.scripted_mode == "bathing":
            bath_bg = load_image(self.bathroom_bg)
            clip_rect = pygame.Rect(38, 51, 43, 17)
            lcd.blit(bath_bg, (38, 51), area=clip_rect)
            for b in self.foam_bubbles:
                by = b["y"] + math.sin(self.flip_tick * 5.0 + b["phase"]) * 1.5
                f_img = self.foam_single_img
                if int((self.flip_tick + b["phase"]) * 3) % 2 == 1:
                    f_img = pygame.transform.flip(f_img, True, False)
                lcd.blit(f_img, (int(b["x"] - 8), int(by - 8)))

        # 6. Nếu đang đánh răng: vẽ bàn chải đánh răng + bọt kem đánh răng
        if self.scripted_mode == "brushing":
            tb_x = int(self.x + cs // 2 - 6 + math.cos(self.flip_tick * 16) * 4)
            tb_y = int(self.y + cs // 3 + math.sin(self.flip_tick * 16) * 2)
            lcd.blit(self.toothbrush_img, (tb_x, tb_y))
            lcd.blit(self.foam_single_img, (int(self.x + cs // 2 - 4), int(self.y + cs // 3)))

        # 7. Nếu đang ăn trong bếp: vẽ món ăn từ foods_on.png trên bàn (3 nấc cắn)
        if self.scripted_mode == "feeding" and self.scripted_timer < 3.3:
            food_cell = self.active_food_sprite + self.active_food_bite
            food_surf = self.foods_sheet.get_frame(food_cell)
            lcd.blit(food_surf, (36, 44))

        # 8. Nếu đang chơi đồ chơi (Items từ items.png)
        if self.scripted_mode == "playing_item":
            item_surf = self.items_sheet.get_frame(self.active_item_sprite)
            iy = int(62 + abs(math.sin(self.flip_tick * 10)) * -8)
            lcd.blit(item_surf, (56, iy))

        # 9. Nếu đang tổ chức đám cưới (Wedding overlay)
        if self.scene == "wedding":
            lcd.blit(self.wedding_overlay_img, (0, 0))

        # 10. Nếu đang quét nhà: vẽ máy hút bụi cleaner.png
        if self.scripted_mode == "cleaning":
            c_img = self.cleaner_img
            if int(self.flip_tick * 4) % 2 == 1:
                c_img = pygame.transform.flip(c_img, False, True)
            lcd.blit(c_img, (int(self.mop_x), 0))

        # 11. Bong bóng suy nghĩ (Current Want) khi người chơi kiểm tra Pet muốn gì
        if self.thought_timer > 0 and self.current_want:
            bx = int(max(4, min(64, self.x - 4)))
            by = int(max(2, self.y - 28))
            lcd.blit(self.thought_bubble_img, (bx, by))
            if self.current_want["type"] == "food":
                w_surf = self.foods_sheet.get_frame(self.current_want["sprite"])
            else:
                w_surf = self.items_sheet.get_frame(self.current_want["sprite"])
            w_small = pygame.transform.scale(w_surf, (16, 16))
            lcd.blit(w_small, (bx + 6, by + 4))

        # 12. Overlays trạng thái (Bẩn, Buồn đi vệ sinh, Đau răng, Đau ốm, Vui vẻ)
        if self.hygiene < 30 and not self.is_sleeping and not self.scripted_mode:
            st_img = pygame.transform.scale(self.stinky_img, (cs, cs))
            if int(self.flip_tick * 3) % 2 == 1:
                st_img = pygame.transform.flip(st_img, True, False)
            lcd.blit(st_img, (int(self.x), int(self.y)))

        if self.bladder < 25 and not self.is_sleeping and not self.scripted_mode:
            nt_img = pygame.transform.scale(self.needstoilet_img, (cs, cs))
            lcd.blit(nt_img, (int(self.x), int(self.y)))

        if self.has_toothache and not self.is_sleeping:
            lcd.blit(self.toothache_img, (int(self.x), int(self.y)))

        if self.is_sick and self.scene == "home":
            sk_img = self.sickness_img
            if int(self.flip_tick * 2) % 2 == 1:
                sk_img = pygame.transform.flip(sk_img, True, False)
            lcd.blit(sk_img, (0, 0))

        if self.state == "cheering":
            lcd.blit(self.happy_icon, (10, 10))
        elif self.state == "shocked":
            lcd.blit(self.exclaim_icon, (int(self.x + cs // 2 - 4), int(self.y - 10)))

        # 13. Lớp tối phòng ngủ khi tắt đèn (dark_overlay.png)
        if self.is_sleeping and self.scene == "home":
            dark = self.dark_overlay.copy()
            dark.set_alpha(210)
            lcd.blit(dark, (0, 0))

        # 14. Vẽ các hạt bay lên (Zzz, Trái tim, Mũi tên xanh)
        for p in self.particles:
            lcd.blit(p["img"], (int(p["x"]), int(p["y"])))

    def to_dict(self) -> dict:
        return {
            "pet_name": self.name,
            "stage": self.stage,
            "generation": self.generation,
            "gender": self.gender,
            "char_idx": self.char_idx,
            "character_file": self.character_file,
            "level": self.level,
            "exp": self.exp,
            "gold": self.gold,
            "hunger": round(self.hunger, 1),
            "energy": round(self.energy, 1),
            "hygiene": round(self.hygiene, 1),
            "happiness": round(self.happiness, 1),
            "health": round(self.health, 1),
            "discipline": round(self.discipline, 1),
            "skill_expression": round(self.skill_expression, 1),
            "skill_logic": round(self.skill_logic, 1),
            "skill_endurance": round(self.skill_endurance, 1),
            "age_seconds": int(self.age_seconds),
            "room_bg": self.room_bg,
            "equipped_accessories": self.equipped_accessories,
            "placed_furniture": self.placed_furniture,
            "unlocked_characters": self.unlocked_characters,
            "family_history": self.family_history,
        }

    def load_from_dict(self, data: dict):
        if not data:
            return
        self.name = data.get("pet_name", self.name)
        self.stage = max(1, min(len(STAGE_INFO) - 1, data.get("stage", self.stage)))
        self.generation = data.get("generation", self.generation)
        raw_gender = data.get("gender", self.gender)
        self.gender = {"BOY": "BÉ TRAI", "GIRL": "BÉ GÁI"}.get(raw_gender, raw_gender)
        self.char_idx = data.get("char_idx", self.char_idx)
        self.level = data.get("level", self.level)
        self.exp = data.get("exp", self.exp)
        self.gold = data.get("gold", self.gold)
        self.hunger = data.get("hunger", self.hunger)
        self.energy = data.get("energy", self.energy)
        self.hygiene = data.get("hygiene", self.hygiene)
        self.happiness = data.get("happiness", self.happiness)
        self.health = data.get("health", self.health)
        self.discipline = data.get("discipline", self.discipline)
        self.skill_expression = data.get("skill_expression", self.skill_expression)
        self.skill_logic = data.get("skill_logic", self.skill_logic)
        self.skill_endurance = data.get("skill_endurance", self.skill_endurance)
        self.age_seconds = data.get("age_seconds", self.age_seconds)
        self.room_bg = data.get("room_bg", self.room_bg)
        self.equipped_accessories = data.get("equipped_accessories", self.equipped_accessories)
        self.placed_furniture = data.get("placed_furniture", self.placed_furniture)
        self.unlocked_characters = data.get("unlocked_characters", self.unlocked_characters)
        self.family_history = data.get("family_history", self.family_history)
        self._load_stage_sprite()
