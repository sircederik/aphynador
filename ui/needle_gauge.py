from __future__ import annotations
from ui.compat import border_all

import math
import flet as ft
import flet.canvas as cv

from ui.theme import AppPalette, DARK_PALETTE


def cents_to_normalized(cents: float, mode: str = "auto") -> float:
    """
    Mapea la desviación en cents al rango normalizado [-1.0, +1.0]:
    - mode == 'auto': lineal en [-50, +50] cents.
    - mode == 'manual': escala no lineal en tres tramos [-500, +500] cents
      (0..±20 c fino, ±20..±100 c medio, ±100..±500 c por semitonos).
    """
    sign = -1.0 if cents < 0.0 else 1.0
    mag = abs(cents)

    if mode == "auto":
        return sign * (min(50.0, mag) / 50.0)

    if mag <= 20.0:
        norm = (mag / 20.0) * 0.20
    elif mag <= 100.0:
        norm = 0.20 + ((mag - 20.0) / 80.0) * 0.40
    else:
        norm = 0.60 + ((min(500.0, mag) - 100.0) / 400.0) * 0.40
    return sign * norm


class BallisticNeedlePhysics:
    """
    Simulador físico masa-resorte-amortiguador para que la aguja emule
    un galvanómetro analógico real sin vibraciones bruscas.
    """

    def __init__(
        self,
        stiffness: float = 110.0,
        damping: float = 17.5,
        rest_position: float = -1.0,
    ) -> None:
        self.stiffness = stiffness
        self.damping = damping
        self.rest_position = rest_position
        self.position: float = rest_position
        self.velocity: float = 0.0

    def step(self, target: float | None, dt: float) -> float:
        goal = self.rest_position if target is None else max(-1.05, min(1.05, target))
        dt_clamped = max(0.001, min(0.05, dt))

        # Integración semi-implícita de Euler
        force = -self.stiffness * (self.position - goal) - self.damping * self.velocity
        self.velocity += force * dt_clamped
        self.position += self.velocity * dt_clamped
        self.position = max(-1.08, min(1.08, self.position))
        return self.position


class AnalogNeedleGauge(ft.Container):
    """
    Cuadrante analógico dual (AUTO ±50 c arriba / MANUAL ±500 c abajo)
    con aguja balística renderizada en Canvas acelerado.
    """

    def __init__(
        self,
        width: float = 460,
        height: float = 230,
        palette: AppPalette = DARK_PALETTE,
    ) -> None:
        super().__init__(width=width, height=height, border_radius=14)
        self.gauge_w = width
        self.gauge_h = height
        self.palette = palette
        self.mode: str = "auto"
        self.physics = BallisticNeedlePhysics(rest_position=-1.0)
        self._last_cents: float | None = None

        self.canvas = cv.Canvas(width=width, height=height, shapes=[])
        self.lbl_auto_tag = ft.Text("AUTO CENT", size=10, weight=ft.FontWeight.BOLD)
        self.lbl_manual_tag = ft.Text("MANUAL", size=10, weight=ft.FontWeight.BOLD)
        self.lbl_flat = ft.Text("♭ ▶", size=18, weight=ft.FontWeight.BOLD)
        self.lbl_sharp = ft.Text("◀ ♯", size=18, weight=ft.FontWeight.BOLD)

        # Etiquetas numéricas superiores (AUTO) e inferiores (MANUAL)
        self._scale_labels: list[ft.Control] = self._build_scale_labels()

        self.content = ft.Stack(
            width=width,
            height=height,
            controls=[
                self.canvas,
                *self._scale_labels,
                ft.Container(content=self.lbl_auto_tag, left=18, top=22),
                ft.Container(content=self.lbl_manual_tag, left=18, top=115),
                ft.Container(content=self.lbl_flat, left=64, bottom=24),
                ft.Container(content=self.lbl_sharp, right=64, bottom=24),
            ],
        )
        self.apply_palette(palette)
        self.redraw()

    def _build_scale_labels(self) -> list[ft.Control]:
        cx = self.gauge_w / 2.0
        cy = self.gauge_h * 0.90
        r_upper = self.gauge_h * 0.76
        r_lower = self.gauge_h * 0.46
        max_angle = math.radians(48.0)

        items: list[ft.Control] = []
        upper_marks = [(-1.0, "-50"), (-0.4, "-20"), (0.0, "0"), (0.4, "+20"), (1.0, "+50")]
        for norm, text in upper_marks:
            theta = norm * max_angle
            x = cx + r_upper * math.sin(theta) - 14
            y = cy - r_upper * math.cos(theta) - 10
            items.append(
                ft.Container(
                    content=ft.Text(text, size=11, weight=ft.FontWeight.W_600),
                    left=x,
                    top=y,
                )
            )

        lower_marks = [
            (-1.0, "-500"),
            (-0.6, "-100"),
            (-0.2, "-20"),
            (0.2, "+20"),
            (0.6, "+100"),
            (1.0, "+500"),
        ]
        for norm, text in lower_marks:
            theta = norm * max_angle
            x = cx + r_lower * math.sin(theta) - 16
            y = cy - r_lower * math.cos(theta) - 4
            items.append(
                ft.Container(
                    content=ft.Text(text, size=10),
                    left=x,
                    top=y,
                )
            )
        return items

    def apply_palette(self, palette: AppPalette) -> None:
        self.palette = palette
        self.bgcolor = palette.dial_face
        self.border = border_all(1.5, palette.dial_border)
        self.lbl_auto_tag.color = palette.accent if self.mode == "auto" else palette.text_secondary
        self.lbl_manual_tag.color = palette.accent if self.mode == "manual" else palette.text_secondary
        self.lbl_flat.color = palette.text_secondary
        self.lbl_sharp.color = palette.text_secondary
        for item in self._scale_labels:
            if isinstance(item, ft.Container) and isinstance(item.content, ft.Text):
                item.content.color = palette.text_primary

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.lbl_auto_tag.color = self.palette.accent if mode == "auto" else self.palette.text_secondary
        self.lbl_manual_tag.color = self.palette.accent if mode == "manual" else self.palette.text_secondary

    def tick_physics(self, cents_diff: float | None, dt: float) -> None:
        self._last_cents = cents_diff
        target_norm = None if cents_diff is None else cents_to_normalized(cents_diff, self.mode)
        self.physics.step(target_norm, dt)
        self.redraw()

    def redraw(self) -> None:
        cx = self.gauge_w / 2.0
        cy = self.gauge_h * 0.90
        r_outer = self.gauge_h * 0.67
        r_mid = self.gauge_h * 0.59
        r_inner = self.gauge_h * 0.52
        max_angle = math.radians(48.0)

        shapes: list[cv.Shape] = []
        major_paint = ft.Paint(color=self.palette.tick_major, stroke_width=2.0, style=ft.PaintingStyle.STROKE)
        minor_paint = ft.Paint(color=self.palette.tick_minor, stroke_width=1.2, style=ft.PaintingStyle.STROKE)
        center_paint = ft.Paint(color=self.palette.in_tune_color, stroke_width=3.0, style=ft.PaintingStyle.STROKE)

        # 21 divisiones uniformes en ángulo (-1.0 a +1.0 en pasos de 0.1)
        for i in range(-10, 11):
            norm = i / 10.0
            theta = norm * max_angle
            sin_t = math.sin(theta)
            cos_t = math.cos(theta)

            is_center = i == 0
            is_upper_major = (i % 2 == 0)

            r1 = r_outer if (is_upper_major or is_center) else r_mid
            r2 = r_inner
            paint = center_paint if is_center else (major_paint if is_upper_major else minor_paint)

            shapes.append(
                cv.Line(
                    cx + r1 * sin_t,
                    cy - r1 * cos_t,
                    cx + r2 * sin_t,
                    cy - r2 * cos_t,
                    paint=paint,
                )
            )

        # Color de la aguja según proximidad al centro
        if self._last_cents is not None and abs(self._last_cents) <= 2.5:
            needle_hex = self.palette.in_tune_color
        elif self._last_cents is not None and abs(self._last_cents) <= 10.0:
            needle_hex = self.palette.near_tune_color
        else:
            needle_hex = self.palette.needle_color

        needle_theta = self.physics.position * max_angle
        needle_len = self.gauge_h * 0.72
        nx = cx + needle_len * math.sin(needle_theta)
        ny = cy - needle_len * math.cos(needle_theta)

        shapes.append(
            cv.Line(
                cx,
                cy,
                nx,
                ny,
                paint=ft.Paint(color=needle_hex, stroke_width=3.0, style=ft.PaintingStyle.STROKE),
            )
        )
        # Pivote inferior
        shapes.append(
            cv.Circle(
                cx,
                cy,
                10,
                paint=ft.Paint(color=self.palette.dial_border, style=ft.PaintingStyle.FILL),
            )
        )

        self.canvas.shapes = shapes
