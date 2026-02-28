"""
BUSCAMINAS CLÁSICO
==================
Un juego de Buscaminas con interfaz gráfica en Pygame,
efectos de partículas, explosiones y sonidos sintetizados.

Controles:
  - Clic izquierdo: Revelar celda
  - Clic derecho: Colocar/quitar bandera
  - R: Reiniciar partida
  - ESC: Volver al menú
"""

import pygame
import numpy as np
import random
import math
import sys
import time

# ──────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────
CELL_SIZE = 36
HEADER_HEIGHT = 60
FPS = 60

# Dificultades: (columnas, filas, minas)
DIFFICULTIES = {
    "Fácil":   (9, 9, 10),
    "Medio":   (16, 16, 40),
    "Difícil": (30, 16, 99),
}

# Paleta de colores
BG_COLOR          = (30, 30, 46)
HEADER_BG         = (24, 24, 37)
CELL_HIDDEN       = (137, 180, 250)
CELL_HIDDEN_HOVER = (166, 200, 255)
CELL_HIDDEN_DARK  = (116, 155, 220)
CELL_REVEALED     = (49, 50, 68)
CELL_REVEALED_LT  = (69, 71, 90)
CELL_BORDER       = (88, 91, 112)
MINE_COLOR        = (243, 139, 168)
FLAG_RED          = (235, 80, 80)
FLAG_POLE         = (205, 214, 244)
TEXT_COLOR         = (205, 214, 244)
SUBTEXT_COLOR     = (147, 153, 178)
TIMER_COLOR       = (250, 179, 135)
MINE_COUNT_COLOR  = (166, 227, 161)
WIN_COLOR         = (166, 227, 161)
LOSE_COLOR        = (243, 139, 168)

# Colores de los números por valor (1-8)
NUM_COLORS = {
    1: (137, 180, 250),  # azul
    2: (166, 227, 161),  # verde
    3: (243, 139, 168),  # rojo
    4: (203, 166, 247),  # morado
    5: (250, 179, 135),  # naranja
    6: (148, 226, 213),  # cyan
    7: (245, 224, 220),  # blanco rosado
    8: (186, 194, 222),  # gris claro
}

# ──────────────────────────────────────────────
# GENERADOR DE SONIDOS
# ──────────────────────────────────────────────
class SoundGenerator:
    """Genera sonidos sintetizados con numpy + pygame."""

    def __init__(self):
        pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
        self.sample_rate = 44100
        self.sounds = {}
        self._generate_all()

    def _make_sound(self, samples: np.ndarray) -> pygame.mixer.Sound:
        """Convierte un array numpy en un Sound de pygame."""
        samples = np.clip(samples, -1.0, 1.0)
        samples_int = (samples * 32767).astype(np.int16)
        return pygame.mixer.Sound(buffer=samples_int.tobytes())

    def _generate_all(self):
        sr = self.sample_rate

        # ── Sonido de clic ──
        dur = 0.08
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        click = np.sin(2 * np.pi * 800 * t) * np.exp(-t * 50)
        click += np.sin(2 * np.pi * 1200 * t) * np.exp(-t * 70) * 0.5
        self.sounds["click"] = self._make_sound(click * 0.6)

        # ── Sonido de bandera ──
        dur = 0.12
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        flag = np.sin(2 * np.pi * 600 * t) * np.exp(-t * 30)
        flag += np.sin(2 * np.pi * 900 * t) * np.exp(-t * 40) * 0.4
        self.sounds["flag"] = self._make_sound(flag * 0.5)

        # ── Sonido de explosión ──
        dur = 0.6
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        noise = np.random.uniform(-1, 1, len(t))
        env = np.exp(-t * 5)
        boom = np.sin(2 * np.pi * 80 * t) * env * 0.7
        boom += noise * env * 0.5
        boom += np.sin(2 * np.pi * 150 * t * np.exp(-t * 3)) * env * 0.3
        self.sounds["explosion"] = self._make_sound(boom * 0.8)

        # ── Sonido de victoria ──
        dur = 1.2
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        notes = [523, 659, 784, 1047]  # C5, E5, G5, C6
        win = np.zeros_like(t)
        seg_len = len(t) // len(notes)
        for i, freq in enumerate(notes):
            start = i * seg_len
            end = start + seg_len
            seg_t = np.linspace(0, seg_len / sr, seg_len, endpoint=False)
            seg = np.sin(2 * np.pi * freq * seg_t) * np.exp(-seg_t * 3)
            seg += np.sin(2 * np.pi * freq * 2 * seg_t) * np.exp(-seg_t * 4) * 0.3
            win[start:end] = seg
        self.sounds["win"] = self._make_sound(win * 0.5)

        # ── Sonido de revelar área grande ──
        dur = 0.15
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        sweep = np.sin(2 * np.pi * (400 + 600 * t / dur) * t) * np.exp(-t * 20)
        self.sounds["sweep"] = self._make_sound(sweep * 0.4)

    def play(self, name: str):
        if name in self.sounds:
            self.sounds[name].play()


# ──────────────────────────────────────────────
# PARTÍCULAS
# ──────────────────────────────────────────────
class Particle:
    """Una partícula individual con física simple."""

    def __init__(self, x, y, vx, vy, color, life, size=3, gravity=200):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size
        self.gravity = gravity

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.life -= dt

    @property
    def alive(self):
        return self.life > 0

    @property
    def alpha(self):
        return max(0, self.life / self.max_life)

    def draw(self, surface):
        if not self.alive:
            return
        a = self.alpha
        current_size = max(1, int(self.size * a))
        r, g, b = self.color
        # Mezclar con fondo para simular transparencia
        r2 = int(r * a + BG_COLOR[0] * (1 - a))
        g2 = int(g * a + BG_COLOR[1] * (1 - a))
        b2 = int(b * a + BG_COLOR[2] * (1 - a))
        pygame.draw.circle(surface, (r2, g2, b2), (int(self.x), int(self.y)), current_size)


class ParticleSystem:
    """Gestiona todas las partículas activas."""

    def __init__(self):
        self.particles: list[Particle] = []

    def emit_explosion(self, x, y, count=40):
        """Explosión radial de partículas rojas/naranjas."""
        colors = [
            (243, 139, 168), (250, 179, 135), (249, 226, 175),
            (235, 80, 80), (255, 160, 60), (255, 255, 180),
        ]
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(80, 350)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            color = random.choice(colors)
            life = random.uniform(0.4, 1.2)
            size = random.randint(2, 5)
            self.particles.append(Particle(x, y, vx, vy, color, life, size, gravity=150))

    def emit_click_ripple(self, x, y, count=8):
        """Pequeña onda radial al hacer clic."""
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(30, 100)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            color = (137, 180, 250)
            self.particles.append(Particle(x, y, vx, vy, color, 0.3, 2, gravity=0))

    def emit_confetti(self, width, count=80):
        """Confeti cayendo desde arriba para victoria."""
        colors = [
            (243, 139, 168), (166, 227, 161), (137, 180, 250),
            (250, 179, 135), (203, 166, 247), (148, 226, 213),
            (249, 226, 175), (245, 194, 231),
        ]
        for _ in range(count):
            x = random.uniform(0, width)
            y = random.uniform(-50, -10)
            vx = random.uniform(-40, 40)
            vy = random.uniform(60, 200)
            color = random.choice(colors)
            life = random.uniform(2.0, 4.0)
            size = random.randint(3, 6)
            self.particles.append(Particle(x, y, vx, vy, color, life, size, gravity=80))

    def update(self, dt):
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.alive]

    def draw(self, surface):
        for p in self.particles:
            p.draw(surface)


# ──────────────────────────────────────────────
# EFECTO DE ONDA (SHOCKWAVE)
# ──────────────────────────────────────────────
class Shockwave:
    """Onda expansiva visual."""

    def __init__(self, x, y, max_radius=120, duration=0.5, color=(243, 139, 168)):
        self.x = x
        self.y = y
        self.max_radius = max_radius
        self.duration = duration
        self.color = color
        self.elapsed = 0

    @property
    def alive(self):
        return self.elapsed < self.duration

    def update(self, dt):
        self.elapsed += dt

    def draw(self, surface):
        if not self.alive:
            return
        progress = self.elapsed / self.duration
        radius = int(self.max_radius * progress)
        alpha = 1 - progress
        width = max(1, int(4 * (1 - progress)))
        r, g, b = self.color
        r2 = int(r * alpha + BG_COLOR[0] * (1 - alpha))
        g2 = int(g * alpha + BG_COLOR[1] * (1 - alpha))
        b2 = int(b * alpha + BG_COLOR[2] * (1 - alpha))
        if radius > 0:
            pygame.draw.circle(surface, (r2, g2, b2), (self.x, self.y), radius, width)


# ──────────────────────────────────────────────
# CELDA ANIMADA
# ──────────────────────────────────────────────
class CellAnimation:
    """Animación de revelado de celda."""

    def __init__(self, row, col, delay=0):
        self.row = row
        self.col = col
        self.delay = delay
        self.elapsed = 0
        self.duration = 0.15
        self.done = False

    def update(self, dt):
        self.elapsed += dt
        if self.elapsed >= self.delay + self.duration:
            self.done = True

    @property
    def scale(self):
        """Retorna escala 0..1 para animación de encogimiento/crecimiento."""
        t = self.elapsed - self.delay
        if t < 0:
            return 1.0
        progress = min(1.0, t / self.duration)
        # ease-out bounce simple
        if progress < 0.5:
            return 1.0 - progress * 0.4
        else:
            return 0.8 + (progress - 0.5) * 0.4


# ──────────────────────────────────────────────
# TABLERO (LÓGICA)
# ──────────────────────────────────────────────
class Board:
    """Lógica del tablero de buscaminas."""

    STATE_HIDDEN = 0
    STATE_REVEALED = 1
    STATE_FLAGGED = 2

    def __init__(self, cols, rows, num_mines):
        self.cols = cols
        self.rows = rows
        self.num_mines = num_mines
        self.mines = set()
        self.grid = [[0] * cols for _ in range(rows)]   # número de minas adyacentes
        self.state = [[self.STATE_HIDDEN] * cols for _ in range(rows)]
        self.game_over = False
        self.won = False
        self.first_click = True
        self.flags_placed = 0
        self.cells_revealed = 0

    def place_mines(self, safe_row, safe_col):
        """Coloca minas evitando la celda segura y sus adyacentes."""
        safe_zone = set()
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                r, c = safe_row + dr, safe_col + dc
                if 0 <= r < self.rows and 0 <= c < self.cols:
                    safe_zone.add((r, c))

        all_cells = [(r, c) for r in range(self.rows) for c in range(self.cols)
                     if (r, c) not in safe_zone]
        self.mines = set(random.sample(all_cells, min(self.num_mines, len(all_cells))))

        # Calcular números
        for (mr, mc) in self.mines:
            for dr in range(-1, 2):
                for dc in range(-1, 2):
                    r, c = mr + dr, mc + dc
                    if 0 <= r < self.rows and 0 <= c < self.cols:
                        self.grid[r][c] += 1

    def reveal(self, row, col) -> list[tuple[int, int]]:
        """Revela una celda. Retorna lista de celdas reveladas."""
        if self.game_over or self.state[row][col] != self.STATE_HIDDEN:
            return []

        if self.first_click:
            self.first_click = False
            self.place_mines(row, col)

        if (row, col) in self.mines:
            self.game_over = True
            self.won = False
            self.state[row][col] = self.STATE_REVEALED
            return [(row, col)]

        # Flood-fill si la celda es 0
        revealed = []
        stack = [(row, col)]
        while stack:
            r, c = stack.pop()
            if not (0 <= r < self.rows and 0 <= c < self.cols):
                continue
            if self.state[r][c] != self.STATE_HIDDEN:
                continue
            self.state[r][c] = self.STATE_REVEALED
            self.cells_revealed += 1
            revealed.append((r, c))
            if self.grid[r][c] == 0:
                for dr in range(-1, 2):
                    for dc in range(-1, 2):
                        if dr == 0 and dc == 0:
                            continue
                        stack.append((r + dr, c + dc))

        self._check_win()
        return revealed

    def toggle_flag(self, row, col) -> bool:
        """Alterna bandera. Retorna True si se cambió."""
        if self.game_over or self.state[row][col] == self.STATE_REVEALED:
            return False
        if self.state[row][col] == self.STATE_FLAGGED:
            self.state[row][col] = self.STATE_HIDDEN
            self.flags_placed -= 1
        else:
            self.state[row][col] = self.STATE_FLAGGED
            self.flags_placed += 1
        return True

    def _check_win(self):
        total_safe = self.rows * self.cols - len(self.mines)
        if self.cells_revealed >= total_safe:
            self.game_over = True
            self.won = True

    @property
    def remaining_mines(self):
        return self.num_mines - self.flags_placed


# ──────────────────────────────────────────────
# JUEGO PRINCIPAL
# ──────────────────────────────────────────────
class Minesweeper:
    """Aplicación principal del juego."""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((500, 500))
        pygame.display.set_caption("💣 Buscaminas")
        self.clock = pygame.time.Clock()
        self.sounds = SoundGenerator()
        self.particles = ParticleSystem()
        self.shockwaves: list[Shockwave] = []
        self.cell_anims: list[CellAnimation] = []
        self.board: Board | None = None
        self.state = "menu"  # "menu" | "playing" | "gameover"
        self.start_time = 0
        self.elapsed_time = 0
        self.hover_cell = (-1, -1)
        self.font_large = None
        self.font_medium = None
        self.font_small = None
        self.font_cell = None
        self.font_emoji = None
        self._load_fonts()
        self._confetti_emitted = False
        self._explosion_emitted = False

        # Botones del menú
        self.menu_buttons: list[tuple[pygame.Rect, str]] = []

    def _load_fonts(self):
        self.font_large = pygame.font.SysFont("Segoe UI", 42, bold=True)
        self.font_medium = pygame.font.SysFont("Segoe UI", 24, bold=True)
        self.font_small = pygame.font.SysFont("Segoe UI", 18)
        self.font_cell = pygame.font.SysFont("Segoe UI", 20, bold=True)
        self.font_emoji = pygame.font.SysFont("Segoe UI Emoji", 22)

    def _resize_for_board(self, cols, rows):
        w = cols * CELL_SIZE + 20
        h = rows * CELL_SIZE + HEADER_HEIGHT + 30
        self.screen = pygame.display.set_mode((w, h))

    def _cell_rect(self, row, col) -> pygame.Rect:
        x = 10 + col * CELL_SIZE
        y = HEADER_HEIGHT + 10 + row * CELL_SIZE
        return pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)

    def _cell_from_pos(self, pos) -> tuple[int, int]:
        mx, my = pos
        col = (mx - 10) // CELL_SIZE
        row = (my - HEADER_HEIGHT - 10) // CELL_SIZE
        if self.board and 0 <= row < self.board.rows and 0 <= col < self.board.cols:
            return row, col
        return -1, -1

    # ── MENÚ ──

    def _draw_menu(self):
        sw, sh = self.screen.get_size()
        self.screen.fill(BG_COLOR)

        # Título
        title = self.font_large.render("💣 BUSCAMINAS", True, TEXT_COLOR)
        self.screen.blit(title, (sw // 2 - title.get_width() // 2, 60))

        subtitle = self.font_small.render("Selecciona una dificultad", True, SUBTEXT_COLOR)
        self.screen.blit(subtitle, (sw // 2 - subtitle.get_width() // 2, 115))

        # Botones
        self.menu_buttons.clear()
        btn_w, btn_h = 260, 60
        start_y = 170
        gap = 20

        difficulty_info = {
            "Fácil": "9×9  ·  10 minas",
            "Medio": "16×16  ·  40 minas",
            "Difícil": "30×16  ·  99 minas",
        }

        btn_colors = [
            ((166, 227, 161), (30, 60, 35)),
            ((250, 179, 135), (60, 40, 25)),
            ((243, 139, 168), (60, 25, 35)),
        ]

        mx, my = pygame.mouse.get_pos()

        for i, (name, info) in enumerate(difficulty_info.items()):
            x = sw // 2 - btn_w // 2
            y = start_y + i * (btn_h + gap)
            rect = pygame.Rect(x, y, btn_w, btn_h)
            self.menu_buttons.append((rect, name))

            fg, bg = btn_colors[i]
            hovered = rect.collidepoint(mx, my)

            # Fondo del botón
            if hovered:
                bg = tuple(min(255, c + 20) for c in bg)
            pygame.draw.rect(self.screen, bg, rect, border_radius=12)
            pygame.draw.rect(self.screen, fg, rect, 2, border_radius=12)

            # Texto
            label = self.font_medium.render(name, True, fg)
            self.screen.blit(label, (rect.centerx - label.get_width() // 2, rect.y + 8))

            detail = self.font_small.render(info, True, SUBTEXT_COLOR)
            self.screen.blit(detail, (rect.centerx - detail.get_width() // 2, rect.y + 35))

        # Footer
        footer = self.font_small.render("Clic izq: Revelar  |  Clic der: Bandera  |  R: Reiniciar", True, SUBTEXT_COLOR)
        self.screen.blit(footer, (sw // 2 - footer.get_width() // 2, sh - 40))

    # ── HEADER DEL JUEGO ──

    def _draw_header(self):
        sw = self.screen.get_width()
        pygame.draw.rect(self.screen, HEADER_BG, (0, 0, sw, HEADER_HEIGHT))
        pygame.draw.line(self.screen, CELL_BORDER, (0, HEADER_HEIGHT - 1), (sw, HEADER_HEIGHT - 1))

        if not self.board:
            return

        # Minas restantes
        mine_text = f"💣 {self.board.remaining_mines:03d}"
        mine_surf = self.font_medium.render(mine_text, True, MINE_COUNT_COLOR)
        self.screen.blit(mine_surf, (15, HEADER_HEIGHT // 2 - mine_surf.get_height() // 2))

        # Temporizador
        timer_text = f"⏱ {int(self.elapsed_time):03d}"
        timer_surf = self.font_medium.render(timer_text, True, TIMER_COLOR)
        self.screen.blit(timer_surf, (sw - timer_surf.get_width() - 15,
                                       HEADER_HEIGHT // 2 - timer_surf.get_height() // 2))

        # Cara central
        if self.board.game_over:
            face = "😵" if not self.board.won else "😎"
        else:
            face = "🙂"
        face_surf = self.font_large.render(face, True, TEXT_COLOR)
        face_rect = face_surf.get_rect(center=(sw // 2, HEADER_HEIGHT // 2))
        self.screen.blit(face_surf, face_rect)

    # ── DIBUJAR TABLERO ──

    def _draw_board(self):
        if not self.board:
            return

        mx, my = pygame.mouse.get_pos()
        self.hover_cell = self._cell_from_pos((mx, my))

        # Mapa de animaciones activas
        anim_map: dict[tuple[int, int], CellAnimation] = {}
        for anim in self.cell_anims:
            if not anim.done:
                anim_map[(anim.row, anim.col)] = anim

        for row in range(self.board.rows):
            for col in range(self.board.cols):
                rect = self._cell_rect(row, col)
                state = self.board.state[row][col]
                is_mine = (row, col) in self.board.mines
                anim = anim_map.get((row, col))

                if state == Board.STATE_HIDDEN or state == Board.STATE_FLAGGED:
                    self._draw_hidden_cell(rect, row, col, state == Board.STATE_FLAGGED)
                elif state == Board.STATE_REVEALED:
                    if is_mine:
                        self._draw_mine_cell(rect)
                    else:
                        self._draw_revealed_cell(rect, self.board.grid[row][col], anim)

        # Si game over, mostrar todas las minas
        if self.board.game_over and not self.board.won:
            for (mr, mc) in self.board.mines:
                if self.board.state[mr][mc] != Board.STATE_REVEALED:
                    rect = self._cell_rect(mr, mc)
                    self._draw_mine_cell(rect, missed=True)

    def _draw_hidden_cell(self, rect: pygame.Rect, row, col, flagged):
        hovered = (row, col) == self.hover_cell and not self.board.game_over

        # Efecto 3D
        color = CELL_HIDDEN_HOVER if hovered else CELL_HIDDEN
        pygame.draw.rect(self.screen, color, rect, border_radius=4)

        # Highlight superior-izquierdo
        highlight = pygame.Rect(rect.x, rect.y, rect.width, 3)
        hl_color = tuple(min(255, c + 40) for c in color)
        pygame.draw.rect(self.screen, hl_color, highlight, border_radius=2)

        # Sombra inferior-derecho
        shadow_h = pygame.Rect(rect.x, rect.bottom - 3, rect.width, 3)
        shadow_v = pygame.Rect(rect.right - 3, rect.y, 3, rect.height)
        sh_color = CELL_HIDDEN_DARK
        pygame.draw.rect(self.screen, sh_color, shadow_h, border_radius=2)
        pygame.draw.rect(self.screen, sh_color, shadow_v, border_radius=2)

        if flagged:
            self._draw_flag(rect)

    def _draw_revealed_cell(self, rect: pygame.Rect, value, anim: CellAnimation | None = None):
        pygame.draw.rect(self.screen, CELL_REVEALED, rect, border_radius=3)
        pygame.draw.rect(self.screen, CELL_BORDER, rect, 1, border_radius=3)

        if value > 0:
            color = NUM_COLORS.get(value, TEXT_COLOR)
            text = self.font_cell.render(str(value), True, color)

            # Animación de escala
            if anim and not anim.done:
                scale = anim.scale
                if scale != 1.0:
                    w = int(text.get_width() * scale)
                    h = int(text.get_height() * scale)
                    if w > 0 and h > 0:
                        text = pygame.transform.smoothscale(text, (w, h))

            text_rect = text.get_rect(center=rect.center)
            self.screen.blit(text, text_rect)

    def _draw_mine_cell(self, rect: pygame.Rect, missed=False):
        bg = (80, 30, 40) if not missed else (60, 30, 35)
        pygame.draw.rect(self.screen, bg, rect, border_radius=3)
        pygame.draw.rect(self.screen, MINE_COLOR, rect, 1, border_radius=3)

        # Dibujar mina
        cx, cy = rect.center
        r = 8
        pygame.draw.circle(self.screen, MINE_COLOR, (cx, cy), r)
        # Líneas de la mina
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x2 = cx + int(math.cos(rad) * (r + 4))
            y2 = cy + int(math.sin(rad) * (r + 4))
            pygame.draw.line(self.screen, MINE_COLOR, (cx, cy), (x2, y2), 2)
        # Brillo
        pygame.draw.circle(self.screen, (255, 255, 255), (cx - 3, cy - 3), 3)

    def _draw_flag(self, rect: pygame.Rect):
        cx, cy = rect.center
        # Mástil
        pygame.draw.line(self.screen, FLAG_POLE, (cx, cy - 10), (cx, cy + 8), 2)
        # Bandera triangular
        points = [(cx, cy - 10), (cx + 10, cy - 5), (cx, cy)]
        pygame.draw.polygon(self.screen, FLAG_RED, points)
        # Base
        pygame.draw.line(self.screen, FLAG_POLE, (cx - 5, cy + 8), (cx + 5, cy + 8), 2)

    # ── GAME OVER OVERLAY ──

    def _draw_game_over_overlay(self):
        if not self.board or not self.board.game_over:
            return

        sw, sh = self.screen.get_size()

        # Overlay semitransparente
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        self.screen.blit(overlay, (0, 0))

        if self.board.won:
            text = "¡VICTORIA! 🎉"
            color = WIN_COLOR
        else:
            text = "¡BOOM! 💥"
            color = LOSE_COLOR

        label = self.font_large.render(text, True, color)
        self.screen.blit(label, (sw // 2 - label.get_width() // 2, sh // 2 - 40))

        hint = self.font_small.render("Presiona R para reiniciar  ·  ESC para menú", True, SUBTEXT_COLOR)
        self.screen.blit(hint, (sw // 2 - hint.get_width() // 2, sh // 2 + 20))

    # ── LÓGICA DEL JUEGO ──

    def start_game(self, difficulty: str):
        cols, rows, mines = DIFFICULTIES[difficulty]
        self._resize_for_board(cols, rows)
        self.board = Board(cols, rows, mines)
        self.state = "playing"
        self.start_time = time.time()
        self.elapsed_time = 0
        self.particles = ParticleSystem()
        self.shockwaves.clear()
        self.cell_anims.clear()
        self._confetti_emitted = False
        self._explosion_emitted = False

    def _handle_left_click(self, row, col):
        if not self.board or self.board.game_over:
            return
        if self.board.state[row][col] == Board.STATE_FLAGGED:
            return

        revealed = self.board.reveal(row, col)
        if not revealed:
            return

        rect = self._cell_rect(row, col)
        cx, cy = rect.center

        if self.board.game_over and not self.board.won:
            # ¡Mina! Explosión
            self.sounds.play("explosion")
            self.particles.emit_explosion(cx, cy, 50)
            self.shockwaves.append(Shockwave(cx, cy, max_radius=150, duration=0.6))
            self._explosion_emitted = True
        else:
            if len(revealed) > 1:
                self.sounds.play("sweep")
            else:
                self.sounds.play("click")
            self.particles.emit_click_ripple(cx, cy)

            # Animaciones de celdas reveladas
            for i, (r, c) in enumerate(revealed):
                delay = i * 0.02  # efecto cascada
                self.cell_anims.append(CellAnimation(r, c, delay))

            if self.board.won:
                self.sounds.play("win")

    def _handle_right_click(self, row, col):
        if not self.board or self.board.game_over:
            return
        if self.board.toggle_flag(row, col):
            self.sounds.play("flag")
            rect = self._cell_rect(row, col)
            self.particles.emit_click_ripple(rect.centerx, rect.centery, count=5)

    # ── BUCLE PRINCIPAL ──

    def run(self):
        running = True

        # Tamaño inicial para el menú
        self.screen = pygame.display.set_mode((500, 450))

        while running:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.state != "menu":
                            self.state = "menu"
                            self.screen = pygame.display.set_mode((500, 450))
                            self.particles = ParticleSystem()
                            self.shockwaves.clear()
                            self.cell_anims.clear()
                    elif event.key == pygame.K_r:
                        if self.board:
                            cols, rows, mines = self.board.cols, self.board.rows, self.board.num_mines
                            diff_name = None
                            for name, (c, r, m) in DIFFICULTIES.items():
                                if c == cols and r == rows and m == mines:
                                    diff_name = name
                                    break
                            if diff_name:
                                self.start_game(diff_name)

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.state == "menu":
                        for rect, name in self.menu_buttons:
                            if rect.collidepoint(event.pos):
                                self.start_game(name)
                                self.sounds.play("click")
                                break
                    elif self.state == "playing" and self.board:
                        row, col = self._cell_from_pos(event.pos)
                        if row >= 0 and col >= 0:
                            if event.button == 1:
                                self._handle_left_click(row, col)
                            elif event.button == 3:
                                self._handle_right_click(row, col)

            # Actualizar
            if self.state == "playing" and self.board and not self.board.game_over:
                self.elapsed_time = time.time() - self.start_time

            self.particles.update(dt)
            self.shockwaves = [sw for sw in self.shockwaves if sw.alive]
            for sw in self.shockwaves:
                sw.update(dt)
            self.cell_anims = [a for a in self.cell_anims if not a.done]
            for a in self.cell_anims:
                a.update(dt)

            # Confetti continuo durante victoria
            if (self.state == "playing" and self.board and self.board.game_over
                    and self.board.won and not self._confetti_emitted):
                self.particles.emit_confetti(self.screen.get_width(), 100)
                self._confetti_emitted = True

            # Dibujar
            self.screen.fill(BG_COLOR)

            if self.state == "menu":
                self._draw_menu()
            elif self.state == "playing":
                self._draw_header()
                self._draw_board()
                if self.board and self.board.game_over:
                    self._draw_game_over_overlay()

            # Efectos encima de todo
            for sw in self.shockwaves:
                sw.draw(self.screen)
            self.particles.draw(self.screen)

            pygame.display.flip()

        pygame.quit()
        sys.exit()


# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    game = Minesweeper()
    game.run()
