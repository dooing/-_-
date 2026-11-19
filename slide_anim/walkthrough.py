"""스크린샷 단계별 설명 애니메이션 엔진 (Manim + manim-slides).

캡처 이미지 위에서 카메라가 단계별로 이동/확대하고, 강조 박스와 설명 카드가 나타난다.
각 단계 끝에서 멈추고, 스페이스바(또는 클릭)를 누르면 다음 단계 애니메이션이 재생된다.

사용 방법은 demo_deck.py 와 README.md 참고.
"""
from __future__ import annotations

import html
import inspect
import math
import re
from dataclasses import dataclass
from pathlib import Path

import manimpango
import numpy as np
from manim import (
    BOLD,
    DOWN,
    LEFT,
    ORIGIN,
    RIGHT,
    UL,
    UP,
    UR,
    Circle,
    Create,
    Cutout,
    Dot,
    FadeIn,
    FadeOut,
    GrowFromEdge,
    ImageMobject,
    LaggedStart,
    ManimColor,
    Line,
    MarkupText,
    Mobject,
    Rectangle,
    RoundedRectangle,
    Text,
    UpdateFromAlphaFunc,
    ValueTracker,
    VGroup,
    config,
    rate_functions,
)
from manim_slides import Slide
from PIL import Image, ImageDraw

# 이 엔진은 업데이터로 매 프레임을 그리므로, Manim 의 부분 영상 캐시가 코드 변경을 감지하지 못한다.
# 수정한 내용이 항상 반영되도록 캐시를 끈다.
config.disable_caching = True

# --------------------------------------------------------------------------------------
# 테마
# --------------------------------------------------------------------------------------
THEMES = {
    "dark": dict(
        bg="#0B1020", surface="#141C30", surface_stroke="#2A3550", text="#EEF2F8",
        muted="#8D97AD", accent="#4CC9F0", on_accent="#06202B", dim_color="#05070F",
        dim=0.8, window_bar="#1C2540", window_stroke="#33405F", window_label="#8D97AD",
        shadow="#000000", dots=("#FF5F57", "#FEBC2E", "#28C840"),
    ),
    "light": dict(
        bg="#EEF2F7", surface="#FFFFFF", surface_stroke="#D5DCE6", text="#0F172A",
        muted="#64748B", accent="#2563EB", on_accent="#FFFFFF", dim_color="#E7ECF3",
        dim=0.80, window_bar="#E2E8F0", window_stroke="#CBD5E1", window_label="#64748B",
        shadow="#0F172A", dots=("#FF5F57", "#FEBC2E", "#28C840"),
    ),
}

FONT_CANDIDATES = [
    "Pretendard", "Noto Sans KR", "Noto Sans CJK KR", "Malgun Gothic",
    "Apple SD Gothic Neo", "AppleGothic", "NanumGothic",
]


def pick_font(candidates=FONT_CANDIDATES) -> str:
    available = set(manimpango.list_fonts())
    for f in candidates:
        if f in available:
            return f
    return ""  # Pango 기본 글꼴


# --------------------------------------------------------------------------------------
# 데이터 구조
# --------------------------------------------------------------------------------------
@dataclass
class Step:
    """한 단계(스페이스바 한 번)에 해당하는 설명.

    image  : 이미지 경로 (덱 파일 기준 상대 경로 가능)
    region : 강조할 영역 (x0, y0, x1, y1), 이미지 픽셀 좌표, 왼쪽 위가 (0, 0)
    title  : 카드 제목
    body   : 카드 본문. **강조** 처럼 쓰면 강조색 굵은 글씨가 된다. 줄바꿈은 자동.
    zoom   : True 면 영역을 확대, False 면 전체 화면을 보여 주며 영역만 강조
    layout : "auto"(기본), "side"(카드가 오른쪽), "bottom"(카드가 아래). auto 는 영역이 더 크게 보이는 쪽을 고른다.
    notes  : 발표자 노트 (생략하면 title + body)
    """

    image: str
    region: tuple[float, float, float, float]
    title: str
    body: str = ""
    zoom: bool = True
    layout: str = "auto"
    notes: str | None = None


@dataclass
class Box:
    """화면 좌표계의 배치 영역 (Manim 단위, 프레임은 가로 14.22, 세로 8)."""

    cx: float
    cy: float
    w: float
    h: float


@dataclass
class Cam:
    """이미지 픽셀 좌표 -> 화면 좌표 변환. 이미지 점 (ix, iy) 가 화면 (sx, sy) 에 오고 배율은 s."""

    s: float
    ix: float
    iy: float
    sx: float
    sy: float

    def pt(self, x, y):
        return np.array([self.sx + (x - self.ix) * self.s, self.sy - (y - self.iy) * self.s, 0.0])

    def rect(self, r):
        """이미지 픽셀 사각형 -> 화면 (left, bottom, right, top)."""
        x0, y0, x1, y1 = r
        a, b = self.pt(x0, y1), self.pt(x1, y0)
        return a[0], a[1], b[0], b[1]


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_rect(a, b, t):
    return tuple(lerp(p, q, t) for p, q in zip(a, b))


def fit_cam(view, box: Box, s_max: float, margin: float = 0.0) -> Cam:
    x0, y0, x1, y1 = view
    s = min((box.w - 2 * margin) / max(x1 - x0, 1), (box.h - 2 * margin) / max(y1 - y0, 1), s_max)
    return Cam(s, (x0 + x1) / 2, (y0 + y1) / 2, box.cx, box.cy)


def lerp_cam(a: Cam, b: Cam, t: float, bump: float) -> Cam:
    s = math.exp(lerp(math.log(a.s), math.log(b.s), t) - bump * math.sin(math.pi * t))
    return Cam(s, lerp(a.ix, b.ix, t), lerp(a.iy, b.iy, t), lerp(a.sx, b.sx, t), lerp(a.sy, b.sy, t))


# --------------------------------------------------------------------------------------
# 레이아웃 (프레임: x -7.11 ~ 7.11, y -4 ~ 4)
# --------------------------------------------------------------------------------------
FW, FH = config.frame_width, config.frame_height
STAGE_SIDE = Box(cx=-2.45, cy=-0.12, w=8.1, h=6.1)  # 카드가 오른쪽일 때 이미지 영역 (왼쪽)
STAGE_BOTTOM = Box(cx=0.0, cy=1.1, w=12.9, h=4.1)  # 카드가 아래일 때 이미지 영역 (위쪽)
FULL = Box(cx=0.0, cy=-0.18, w=12.6, h=6.2)  # 전체 화면 보기
INTRO = Box(cx=5.75, cy=-0.55, w=9.6, h=6.6)  # 표지에서 오른쪽에 걸친 미리보기
CARD_W = 4.75  # 오른쪽 카드
CARD_X = 4.45
CARD_LEFT = CARD_X - CARD_W / 2
CARD_B_W = 12.9  # 아래쪽 카드
CARD_B_TOP = -1.25
ZOOM_MARGIN = 0.45  # 확대할 때 강조 영역 주변 여백 (화면 단위)
LAYOUT_SWITCH = 1.15  # auto 레이아웃: 다른 배치가 이 배율 이상 크게 보일 때만 전환

BAR_PX = 34  # 창 제목 표시줄 높이 (이미지 픽셀 기준)
RADIUS_PX = 14  # 창 모서리 반경 (이미지 픽셀 기준)
HL_PAD = 0.07  # 강조 박스 여백 (화면 단위)
REF_PX_PER_UNIT = 1920 / FW  # 1080p 기준 화면 픽셀/단위 (확대 한계 계산용)


class Walkthrough(Slide):
    """덱 클래스를 만들 때 이 클래스를 상속하고 아래 속성만 바꾸면 된다."""

    THEME = "dark"
    FONT: str | None = None  # None 이면 설치된 한글 글꼴 자동 선택
    EYEBROW = ""
    TITLE = ""
    SUBTITLE = ""
    HEADER: str | None = None  # 단계 진행 중 왼쪽 위 표시 (None 이면 TITLE)
    STEPS: list[Step] = []
    SHOW_RECAP = True
    RECAP_TITLE = "정리"
    MAX_UPSCALE = 2.0  # 원본 1픽셀을 최대 몇 화면 픽셀까지 키울지 (1080p 기준)
    MOVE_TIME = 1.6  # 카메라 이동 시간 (초)

    # ----------------------------------------------------------------------------------
    def construct(self):
        self.th = THEMES[self.THEME]
        self.camera.background_color = ManimColor(self.th["bg"])
        self.font = self.FONT if self.FONT is not None else pick_font()
        self.wait_time_between_slides = 0.1
        self.base_dir = Path(inspect.getfile(type(self))).resolve().parent
        self.s_max = self.MAX_UPSCALE / REF_PX_PER_UNIT
        self._width_cache: dict = {}

        self.layout = "side"
        self.card_layout = "side"
        self._backdrop()
        self._setup_rig()
        self._intro()
        for i, step in enumerate(self.STEPS):
            self._step(i, step)
        if self.SHOW_RECAP:
            self._recap()

    def _backdrop(self):
        """배경의 은은한 빛 번짐."""
        th = self.th
        for pos, n, a in (([-5.8, 3.4, 0], 16, 0.0075), ([6.2, -3.6, 0], 12, 0.006)):
            g = VGroup(*[Circle(radius=0.5 + k * 0.42, stroke_width=0, fill_color=th["accent"], fill_opacity=a)
                         for k in range(n)]).move_to(pos)
            g.set_z_index(0)
            self.add(g)

    # ==================================================================================
    # 리그: 이미지, 창 테두리, 스포트라이트, 강조 박스, 번호 배지를 매 프레임 다시 그린다.
    # ==================================================================================
    def _setup_rig(self):
        th = self.th
        self.img = None
        self.img_path = None
        self.img_size = (1, 1)
        self.img_label = None
        self._op_applied: dict = {}
        self.out = None  # 화면 전환 중 사라지는 이전 이미지 (img, size, label)
        self.out_cam = None
        self.cam = Cam(0.01, 0, 0, 0, 0)
        self.view = None
        self.region = None
        self.badge_num = None
        self._img_cache: dict = {}

        self.t_img = ValueTracker(0)  # 이미지 불투명도
        self.t_out = ValueTracker(0)  # 사라지는 이전 이미지 불투명도
        self.t_dim = ValueTracker(0)  # 스포트라이트 어둡기
        self.t_draw = ValueTracker(0)  # 강조 박스 그려진 정도
        self.t_hl = ValueTracker(1)  # 강조 박스 불투명도
        self.t_badge = ValueTracker(0)  # 번호 배지 크기 (0~1, 튀는 효과로 1 초과 가능)
        self.t_prog = ValueTracker(0)  # 진행 막대
        self.t_chrome = ValueTracker(0)  # 머리글/진행 막대 불투명도

        self.l_shadow = VGroup()
        self.l_window = VGroup()
        self.l_frame = VGroup()
        self.l_overlay = VGroup()
        self.l_hl = VGroup()
        self.l_badge = VGroup()
        self.l_prog = VGroup()

        self.driver = Mobject()
        self.driver.add_updater(lambda m, dt: self._redraw())
        self.add(self.driver, self.l_shadow, self.l_window, self.l_frame, self.l_overlay,
                 self.l_hl, self.l_badge, self.l_prog)

    def _load_image(self, path: str):
        p = Path(path)
        if not p.is_absolute():
            p = self.base_dir / p
        key = str(p)
        if key not in self._img_cache:
            im = Image.open(p).convert("RGBA")
            # 아래쪽 모서리를 둥글게 (위쪽은 창 제목 표시줄이 덮는다)
            mask = Image.new("L", im.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, -RADIUS_PX * 2, im.width - 1, im.height - 1],
                                                   radius=RADIUS_PX, fill=255)
            alpha = np.minimum(np.array(im)[:, :, 3], np.array(mask))
            arr = np.array(im)
            arr[:, :, 3] = alpha
            mob = ImageMobject(arr)
            label = Text(p.name, font=self.font, font_size=24, color=self.th["window_label"])
            self._img_cache[key] = (mob, im.size, label)
        return key, *self._img_cache[key]

    def _set_image(self, path: str):
        if self.img is not None:
            self.remove(self.img)
        key, mob, size, label = self._load_image(path)
        self.img, self.img_size, self.img_label, self.img_path = mob, size, label, path
        self._op_applied.pop(id(mob), None)
        self.img.set_z_index(2)
        self.add(self.img)

    @staticmethod
    def _put(layer, mobs, z):
        # play() 가 시작될 때의 하위 객체들은 그 애니메이션이 끝날 때까지 렌더 목록에 남는다.
        # 교체되는 옛 객체를 투명하게 만들어 잔상이 남지 않게 한다.
        for old in layer.submobjects:
            old.set_opacity(0)
        for m in mobs:
            m.set_z_index(z)
        layer.submobjects = list(mobs)

    def _window(self, img, size, label_src, cam, op):
        """스크린샷 한 장의 위치/불투명도를 갱신하고 그림자, 제목 표시줄, 테두리를 만든다."""
        th = self.th
        w, h = size
        img.scale_to_fit_width(w * cam.s)
        img.move_to(cam.pt(w / 2, h / 2))
        last = self._op_applied.get(id(img))
        if last is None or abs(op - last) > 1e-3:
            img.set_opacity(op)
            self._op_applied[id(img)] = op
        if op <= 0.002:
            return [], [], []
        l, b, r, t = cam.rect((0, 0, w, h))
        bar = BAR_PX * cam.s
        rad = RADIUS_PX * cam.s
        ww, wh = r - l, (t + bar) - b
        center = np.array([(l + r) / 2, (b + t + bar) / 2, 0])
        shadows = [
            RoundedRectangle(width=ww + 2 * grow, height=wh + 2 * grow, corner_radius=rad + grow,
                             stroke_width=0, fill_color=th["shadow"], fill_opacity=a * op).move_to(center + DOWN * 0.12)
            for grow, a in ((0.05, 0.22), (0.14, 0.11), (0.28, 0.05))
        ]
        bar_rect = RoundedRectangle(width=ww, height=bar + rad * 2, corner_radius=rad, stroke_width=0,
                                    fill_color=th["window_bar"], fill_opacity=op)
        bar_rect.move_to([center[0], t + bar - (bar + rad * 2) / 2, 0])
        dots = [
            Circle(radius=6 * cam.s, stroke_width=0, fill_color=c, fill_opacity=op)
            .move_to([l + (22 + 20 * k) * cam.s, t + bar / 2, 0])
            for k, c in enumerate(th["dots"])
        ]
        label = label_src.copy().scale_to_fit_height(12 * cam.s).move_to([center[0], t + bar / 2, 0])
        label.set_opacity(op)
        border = RoundedRectangle(width=ww, height=wh, corner_radius=rad, fill_opacity=0,
                                  stroke_color=th["window_stroke"], stroke_width=1.5,
                                  stroke_opacity=op).move_to(center)
        return shadows, [bar_rect, *dots, label], [border]

    def _hl_rect(self):
        l, b, r, t = self.cam.rect(self.region)
        return l - HL_PAD, b - HL_PAD, r + HL_PAD, t + HL_PAD

    def _redraw(self):
        th, cam = self.th, self.cam
        op = self.t_img.get_value()

        # 이미지 + 창 테두리 ------------------------------------------------------------
        wins = []
        if self.img is not None:
            wins.append((self.img, self.img_size, self.img_label, cam, op))
        if self.out is not None:
            wins.append((*self.out, self.out_cam, self.t_out.get_value()))
        shadows, window, frame = [], [], []
        for args in wins:
            sh, wn, fr = self._window(*args)
            shadows += sh
            window += wn
            frame += fr
        self._put(self.l_shadow, shadows, 1)
        self._put(self.l_window, window, 1)
        self._put(self.l_frame, frame, 3)

        # 스포트라이트 -------------------------------------------------------------------
        dim = self.t_dim.get_value()
        if dim > 0.002:
            full = Rectangle(width=FW + 2, height=FH + 2)
            holes = []
            if self.region is not None:
                l, b, r, t = self._hl_rect()
                if r - l > 0.05 and t - b > 0.05:
                    holes.append(
                        RoundedRectangle(width=r - l, height=t - b, corner_radius=min(0.12, (r - l) / 2, (t - b) / 2))
                        .move_to([(l + r) / 2, (b + t) / 2, 0])
                    )
            overlay = Cutout(full, *holes, fill_color=th["dim_color"], fill_opacity=dim, stroke_width=0)
            self._put(self.l_overlay, [overlay], 4)
        else:
            self._put(self.l_overlay, [], 4)

        # 강조 박스 ----------------------------------------------------------------------
        draw, hl_op = self.t_draw.get_value(), self.t_hl.get_value()
        if self.region is not None and draw > 0.002 and hl_op > 0.002:
            l, b, r, t = self._hl_rect()
            base = RoundedRectangle(width=r - l, height=t - b, corner_radius=min(0.12, (r - l) / 2, (t - b) / 2))
            base.move_to([(l + r) / 2, (b + t) / 2, 0])
            # 왼쪽 위에서부터 그려지도록 시작점을 옮긴다
            parts = []
            for width, a in ((16, 0.10), (8, 0.20), (3.2, 1.0)):
                m = base.copy().set_fill(opacity=0).set_stroke(th["accent"], width=width, opacity=a * hl_op)
                if draw < 0.999:
                    m.pointwise_become_partial(base.copy(), 0, draw)
                    m.set_fill(opacity=0).set_stroke(th["accent"], width=width, opacity=a * hl_op)
                parts.append(m)
            self._put(self.l_hl, parts, 5)
        else:
            self._put(self.l_hl, [], 5)

        # 번호 배지 ----------------------------------------------------------------------
        bs = self.t_badge.get_value()
        if self.region is not None and self.badge_num is not None and bs > 0.01:
            l, b, r, t = self._hl_rect()
            pos = np.array([l, t, 0])
            circ = Circle(radius=0.25, fill_color=th["accent"], fill_opacity=min(1, bs) * hl_op,
                          stroke_color=th["bg"], stroke_width=4, stroke_opacity=min(1, bs) * hl_op)
            num = self.badge_num.copy().set_opacity(min(1, bs) * hl_op)
            g = VGroup(circ, num.move_to(circ)).scale(max(bs, 0.01)).move_to(pos)
            self._put(self.l_badge, list(g), 6)
        else:
            self._put(self.l_badge, [], 6)

        # 진행 막대 ----------------------------------------------------------------------
        co = self.t_chrome.get_value()
        if co > 0.002:
            bands = []
            for y_edge, sign, solid, fade in ((FH / 2, -1, 0.75, 0.3), (-FH / 2, 1, 0.4, 0.25)):
                bands.append(Rectangle(width=FW + 0.2, height=solid, stroke_width=0, fill_color=th["bg"],
                                       fill_opacity=0.9 * co).move_to([0, y_edge + sign * solid / 2, 0]))
                n = 8
                for k in range(n):
                    hgt = fade / n
                    yc = y_edge + sign * (solid + hgt * (k + 0.5))
                    bands.append(Rectangle(width=FW + 0.2, height=hgt * 1.02, stroke_width=0, fill_color=th["bg"],
                                           fill_opacity=0.9 * co * (1 - (k + 1) / (n + 1))).move_to([0, yc, 0]))
            for m in bands:
                m.set_z_index(7)
            y, x0, x1 = -3.78, -6.75, 6.75
            track = Line([x0, y, 0], [x1, y, 0], stroke_color=th["muted"], stroke_width=3, stroke_opacity=0.25 * co)
            p = self.t_prog.get_value()
            fill = Line([x0, y, 0], [x0 + max(p, 0.001) * (x1 - x0), y, 0], stroke_color=th["accent"],
                        stroke_width=3, stroke_opacity=co)
            track.set_z_index(8)
            fill.set_z_index(8)
            for old in self.l_prog.submobjects:
                old.set_opacity(0)
            self.l_prog.submobjects = [*bands, track, fill]
        else:
            self._put(self.l_prog, [], 8)

    # ----------------------------------------------------------------------------------
    def _move(self, view, box: Box, region=None, run_time=None, rate=rate_functions.ease_in_out_cubic,
              margin=0.0):
        """카메라를 view(이미지 픽셀 사각형)가 box 에 꼭 맞도록 이동하는 애니메이션."""
        a = self.cam
        b = fit_cam(view, box, self.s_max, margin)
        bump = 0.0
        if self.view is not None:
            u = (min(self.view[0], view[0]), min(self.view[1], view[1]),
                 max(self.view[2], view[2]), max(self.view[3], view[3]))
            s_need = min(box.w / max(u[2] - u[0], 1), box.h / max(u[3] - u[1], 1))
            s_mid = math.sqrt(a.s * b.s)
            bump = max(0.0, math.log(s_mid / s_need)) * 0.55
        r_a, r_b = self.region, region

        def upd(_m, alpha):
            t = rate(alpha)
            self.cam = lerp_cam(a, b, t, bump)
            if r_a is not None and r_b is not None:
                self.region = lerp_rect(r_a, r_b, t)
            elif r_b is not None:
                self.region = r_b

        self.view = view
        return UpdateFromAlphaFunc(Mobject(), upd, run_time=run_time or self.MOVE_TIME,
                                   rate_func=rate_functions.linear, remover=True)

    def _target(self, step: Step, layout: str):
        box = STAGE_SIDE if layout == "side" else STAGE_BOTTOM
        if step.zoom:
            return step.region, box, ZOOM_MARGIN
        return self._full_view(), box, 0.0

    def _choose_layout(self, step: Step) -> str:
        if step.layout in ("side", "bottom"):
            return step.layout
        scale = {}
        for lay in ("side", "bottom"):
            view, box, margin = self._target(step, lay)
            scale[lay] = fit_cam(view, box, self.s_max, margin).s
        prev = self.layout
        other = "bottom" if prev == "side" else "side"
        return other if scale[other] > scale[prev] * LAYOUT_SWITCH else prev

    def _full_view(self):
        w, h = self.img_size
        return (0, -BAR_PX, w, h)  # 제목 표시줄 포함

    # ==================================================================================
    # 텍스트 도우미
    # ==================================================================================
    def _text_w(self, s, fs, weight="NORMAL"):
        key = (s, fs, weight)
        if key not in self._width_cache:
            plain = s.replace("**", "")
            self._width_cache[key] = Text(plain, font=self.font, font_size=fs, weight=weight).width if plain else 0
        return self._width_cache[key]

    def _wrap(self, s, fs, max_w, weight="NORMAL"):
        lines = []
        for para in s.split("\n"):
            line = ""
            for word in para.split(" "):
                cand = f"{line} {word}".strip()
                if line and self._text_w(cand, fs, weight) > max_w:
                    lines.append(line)
                    line = word
                else:
                    line = cand
            lines.append(line)
        return lines

    def _markup(self, s, color=None):
        esc = html.escape(s, quote=False)
        acc = color or self.th["accent"]
        return re.sub(r"\*\*(.+?)\*\*", rf'<span foreground="{acc}" weight="bold">\1</span>', esc, flags=re.S)

    def _para(self, s, fs, max_w, color, weight="NORMAL", line_spacing=0.9):
        lines = self._wrap(s, fs, max_w, weight)
        mk = self._markup("\n".join(lines))
        if weight == BOLD:
            mk = f'<span weight="bold">{mk}</span>'
        return MarkupText(mk, font=self.font, font_size=fs, color=color, line_spacing=line_spacing)

    def _eyebrow(self, s, fs=16):
        mk = f'<span letter_spacing="1500" weight="bold">{html.escape(s, quote=False)}</span>'
        return MarkupText(mk, font=self.font, font_size=fs, color=self.th["accent"])

    # ==================================================================================
    # 장면 구성
    # ==================================================================================
    def _intro(self):
        th = self.th
        first = self.STEPS[0].image if self.STEPS else None
        parts = []
        if self.EYEBROW:
            parts.append(self._eyebrow(self.EYEBROW, 18))
        title = self._para(self.TITLE, 56, 6.6, th["text"], weight=BOLD, line_spacing=0.8)
        parts.append(title)
        rule = Line(ORIGIN, RIGHT * 1.1, stroke_color=th["accent"], stroke_width=5)
        parts.append(rule)
        if self.SUBTITLE:
            parts.append(self._para(self.SUBTITLE, 24, 6.4, th["muted"]))
        cover = VGroup(*parts).arrange(DOWN, aligned_edge=LEFT, buff=0.34)
        cover.move_to([-6.3 + cover.width / 2, 0.15, 0]).set_z_index(9)
        self.cover = cover

        anims = []
        if first:
            self._set_image(first)
            start = fit_cam(self._full_view(), Box(INTRO.cx + 1.6, INTRO.cy - 0.3, INTRO.w, INTRO.h), self.s_max)
            self.cam = start
            self.view = self._full_view()
            anims.append(self._move(self._full_view(), INTRO, run_time=2.2, rate=rate_functions.ease_out_cubic))
            anims.append(self.t_img.animate(run_time=1.6).set_value(1))

        cover_anims = [FadeIn(p, shift=UP * 0.25) for p in parts]
        cover_anims[parts.index(rule)] = GrowFromEdge(rule, LEFT)
        self.play(*anims, LaggedStart(*cover_anims, lag_ratio=0.22, run_time=1.8))

        # 머리글 (단계 진행 중 표시)
        hdr = self.HEADER if self.HEADER is not None else self.TITLE.replace("\n", " ")
        mark = RoundedRectangle(width=0.16, height=0.16, corner_radius=0.04, stroke_width=0,
                                fill_color=th["accent"], fill_opacity=1)
        htxt = Text(hdr, font=self.font, font_size=18, color=th["muted"])
        self.header = VGroup(mark, htxt).arrange(RIGHT, buff=0.18)
        self.header.move_to([-6.75 + self.header.width / 2, 3.62, 0]).set_z_index(8)
        self.counter = None

        # 2번째 슬라이드: 전체 화면 보기
        self.next_slide(notes="전체 화면 구성 소개")
        anims = [FadeOut(cover, shift=LEFT * 0.4), FadeIn(self.header, shift=DOWN * 0.15),
                 self.t_chrome.animate.set_value(1)]
        if first:
            anims.append(self._move(self._full_view(), FULL, run_time=1.6))
        self.play(*anims, run_time=1.6)

    def _counter(self, i):
        n = len(self.STEPS)
        mk = (f'<span foreground="{self.th["text"]}" weight="bold">{i + 1:02d}</span>'
              f'<span foreground="{self.th["muted"]}">  /  {n:02d}</span>')
        c = MarkupText(mk, font=self.font, font_size=18)
        return c.move_to([6.75 - c.width / 2, 3.62, 0]).set_z_index(8)

    def _card(self, i, step, layout):
        th = self.th
        pad = 0.38 if layout == "side" else 0.34
        left_w = CARD_W - 2 * pad if layout == "side" else 3.6
        label = self._eyebrow(f"STEP {i + 1:02d}", 15)
        title = self._para(step.title, 32, left_w, th["text"], weight=BOLD, line_spacing=0.8)
        rule = Line(ORIGIN, RIGHT * 0.7, stroke_color=th["accent"], stroke_width=4)
        head = VGroup(label, title, rule).arrange(DOWN, aligned_edge=LEFT, buff=0.26)
        rule.shift(UP * 0.05)
        items = [label, title, rule]

        if layout == "side":
            body = self._para(step.body, 21, left_w, th["text"], line_spacing=1.05) if step.body else None
            content = VGroup(head, body).arrange(DOWN, aligned_edge=LEFT, buff=0.26) if body else head
            bg = RoundedRectangle(width=CARD_W, height=content.height + 2 * pad, corner_radius=0.22,
                                  fill_color=th["surface"], fill_opacity=0.96,
                                  stroke_color=th["surface_stroke"], stroke_width=1.5)
            bg.move_to([CARD_X, -0.12, 0])
            content.move_to(bg).align_to(bg, LEFT).shift(RIGHT * pad)
            if body:
                items.append(body)
        else:
            body_w = CARD_B_W - 2 * pad - left_w - 0.7
            body = self._para(step.body, 21, body_w, th["text"], line_spacing=1.05) if step.body else None
            h = max(head.height, body.height if body else 0) + 2 * pad
            bg = RoundedRectangle(width=CARD_B_W, height=h, corner_radius=0.22,
                                  fill_color=th["surface"], fill_opacity=0.96,
                                  stroke_color=th["surface_stroke"], stroke_width=1.5)
            bg.move_to([0, CARD_B_TOP - h / 2, 0])
            head.move_to(bg).align_to(bg, LEFT).shift(RIGHT * pad)
            if body:
                x_div = bg.get_left()[0] + pad + left_w + 0.35
                divider = Line([x_div, bg.get_top()[1] - pad, 0], [x_div, bg.get_bottom()[1] + pad, 0],
                               stroke_color=th["surface_stroke"], stroke_width=1.5)
                body.move_to(bg).align_to(divider, LEFT).shift(RIGHT * 0.35)
                items += [divider, body]
        accent_bar = Line(bg.get_corner(UL) + DOWN * 0.3 + RIGHT * 0.02, bg.get_corner(UL) + DOWN * 0.95 + RIGHT * 0.02,
                          stroke_color=th["accent"], stroke_width=5)
        for m in (bg, accent_bar, *items):
            m.set_z_index(9)
        return bg, accent_bar, items

    def _connector(self, card_bg):
        if self.region is None:
            return None
        l, b, r, t = self._hl_rect()
        if self.card_layout == "side":
            if r > CARD_LEFT - 0.35:
                return None
            y = (b + t) / 2
            p1, p2 = [r, y, 0], [CARD_LEFT, y, 0]
        else:
            top = card_bg.get_top()[1]
            if b < top + 0.35:
                return None
            x = min(max((l + r) / 2, -5.8), 5.8)
            p1, p2 = [x, b, 0], [x, top, 0]
        line = Line(p1, p2, stroke_color=self.th["accent"], stroke_width=2, stroke_opacity=0.85, buff=0.02)
        d1 = Dot(p1, radius=0.06, color=self.th["accent"])
        d2 = Dot(p2, radius=0.05, color=self.th["accent"])
        g = VGroup(line, d1, d2)
        g.set_z_index(8)
        return g

    def _clear_card(self):
        out = []
        if getattr(self, "card_mobs", None):
            d = RIGHT if self.card_layout == "side" else DOWN
            out += [FadeOut(m, shift=d * 0.3) for m in self.card_mobs]
            self.card_mobs = None
        if getattr(self, "conn", None) is not None:
            out.append(FadeOut(self.conn))
            self.conn = None
        return out

    def _step(self, i, step: Step):
        th = self.th
        notes = step.notes or f"{step.title}\n{step.body.replace('**', '')}"
        self.next_slide(notes=notes)

        # 1) 이전 카드 정리 (+ 이미지가 바뀌면 화면 전환)
        out = self._clear_card()
        out.append(self.t_badge.animate.set_value(0))
        if self.img_path != step.image and self.img is not None and self.t_img.get_value() > 0:
            # 현재 화면 전체로 물러난 뒤, 옛 화면은 왼쪽으로 사라지고 새 화면이 오른쪽에서 들어온다
            self.play(*out, self.t_hl.animate.set_value(0), self.t_dim.animate.set_value(0),
                      self._move(self._full_view(), FULL, run_time=1.1), run_time=1.1)
            self.region = None
            self.out = (self.img, self.img_size, self.img_label)
            self.out_cam = a_out = self.cam
            b_out = Cam(a_out.s * 0.9, a_out.ix, a_out.iy, a_out.sx - 2.4, a_out.sy)
            self.t_out.set_value(1)
            self.img = None
            self._set_image(step.image)
            self.t_img.set_value(0)
            self.t_draw.set_value(0)
            self.t_hl.set_value(1)
            self.cam = fit_cam(self._full_view(), Box(FULL.cx + 2.4, FULL.cy, FULL.w * 0.9, FULL.h * 0.9), self.s_max)
            self.view = self._full_view()

            def upd_out(_m, alpha):
                self.out_cam = lerp_cam(a_out, b_out, rate_functions.ease_in_out_cubic(alpha), 0)

            self.play(UpdateFromAlphaFunc(Mobject(), upd_out, rate_func=rate_functions.linear, remover=True),
                      self.t_out.animate.set_value(0), self.t_img.animate.set_value(1),
                      self._move(self._full_view(), FULL), run_time=1.2)
            self.remove(self.out[0])
            self.out = None
        elif self.img_path != step.image:
            if out:
                self.play(*out, run_time=0.4)
            self._set_image(step.image)
            self.t_draw.set_value(0)
            self.t_hl.set_value(1)
            self.cam = fit_cam(self._full_view(), Box(FULL.cx + 1.5, FULL.cy, FULL.w * 0.92, FULL.h * 0.92), self.s_max)
            self.view = self._full_view()
            self.play(self.t_img.animate.set_value(1),
                      self._move(self._full_view(), FULL, run_time=0.7, rate=rate_functions.ease_out_cubic),
                      run_time=0.7)
        else:
            self.play(*out, run_time=0.4)

        # 2) 카메라 이동 (+ 강조 박스 이동)
        self.layout = self._choose_layout(step)
        view, box, margin = self._target(step, self.layout)
        had_hl = self.region is not None and self.t_draw.get_value() > 0.99 and self.t_hl.get_value() > 0.99
        self.badge_num = Text(str(i + 1), font=self.font, font_size=22, weight=BOLD, color=th["on_accent"])
        move = self._move(view, box, region=step.region, margin=margin)
        if had_hl:
            self.play(move, self.t_dim.animate.set_value(th["dim"]), run_time=self.MOVE_TIME)
        else:
            self.t_draw.set_value(0)
            self.t_hl.set_value(1)
            self.play(move, run_time=self.MOVE_TIME)
            self.play(self.t_draw.animate.set_value(1), self.t_dim.animate.set_value(th["dim"]),
                      run_time=0.7, rate_func=rate_functions.ease_in_out_sine)

        # 3) 배지 + 카드 + 머리글 갱신
        bg, accent_bar, items = self._card(i, step, self.layout)
        self.card_layout = self.layout
        self.card_mobs = [bg, accent_bar, *items]
        new_counter = self._counter(i)
        hdr_anims = [FadeIn(new_counter, shift=DOWN * 0.15)]
        if self.counter is not None:
            hdr_anims.append(FadeOut(self.counter, shift=DOWN * 0.15))
        self.counter = new_counter
        text_anims = []
        for m in items:
            if isinstance(m, Line):
                vertical = abs(m.get_vector()[1]) > abs(m.get_vector()[0])
                text_anims.append(GrowFromEdge(m, UP if vertical else LEFT))
            else:
                text_anims.append(FadeIn(m, shift=UP * 0.18))
        self.play(
            self.t_badge.animate(rate_func=rate_functions.ease_out_back).set_value(1),
            FadeIn(bg, shift=(LEFT if self.layout == "side" else UP) * 0.35),
            GrowFromEdge(accent_bar, UP),
            LaggedStart(*text_anims, lag_ratio=0.16),
            *hdr_anims,
            self.t_prog.animate.set_value((i + 1) / len(self.STEPS)),
            run_time=1.1,
        )
        self.conn = self._connector(bg)
        if self.conn is not None:
            self.play(Create(self.conn), run_time=0.4)

    def _recap(self):
        th = self.th
        self.next_slide(notes=self.RECAP_TITLE)
        out = self._clear_card()
        self.play(*out, self.t_badge.animate.set_value(0), self.t_hl.animate.set_value(0),
                  self.t_dim.animate.set_value(0), self._move(self._full_view(), STAGE_SIDE, run_time=1.4), run_time=1.4)
        self.region = None

        # 현재 이미지에 속한 단계 영역들을 번호와 함께 표시
        marks = []
        cur = [(k, s) for k, s in enumerate(self.STEPS) if s.image == self.img_path]
        for k, s in cur:
            l, b, r, t = self.cam.rect(s.region)
            box = RoundedRectangle(width=r - l + 0.06, height=t - b + 0.06, corner_radius=0.08,
                                   stroke_color=th["accent"], stroke_width=2.5, fill_color=th["accent"],
                                   fill_opacity=0.08).move_to([(l + r) / 2, (b + t) / 2, 0])
            badge = VGroup(
                Circle(radius=0.19, fill_color=th["accent"], fill_opacity=1, stroke_color=th["bg"], stroke_width=3),
                Text(str(k + 1), font=self.font, font_size=17, weight=BOLD, color=th["on_accent"]),
            )
            badge[1].move_to(badge[0])
            badge.move_to(box.get_corner(UL))
            marks.append(VGroup(box, badge).set_z_index(6))

        # 정리 카드
        pad = 0.38
        inner = CARD_W - 2 * pad
        rows = []
        for k, s in enumerate(self.STEPS):
            dot = VGroup(Circle(radius=0.17, fill_color=th["accent"], fill_opacity=1, stroke_width=0),
                         Text(str(k + 1), font=self.font, font_size=15, weight=BOLD, color=th["on_accent"]))
            dot[1].move_to(dot[0])
            txt = self._para(s.title, 20, inner - 0.55, th["text"])
            rows.append(VGroup(dot, txt).arrange(RIGHT, buff=0.2, aligned_edge=UP))
        head = self._eyebrow("SUMMARY", 15)
        title = self._para(self.RECAP_TITLE, 32, inner, th["text"], weight=BOLD)
        rule = Line(ORIGIN, RIGHT * 0.7, stroke_color=th["accent"], stroke_width=4)
        lst = VGroup(*rows).arrange(DOWN, aligned_edge=LEFT, buff=0.2)
        content = VGroup(head, title, rule, lst).arrange(DOWN, aligned_edge=LEFT, buff=0.26)
        bg = RoundedRectangle(width=CARD_W, height=content.height + 2 * pad, corner_radius=0.22,
                              fill_color=th["surface"], fill_opacity=0.96, stroke_color=th["surface_stroke"],
                              stroke_width=1.5).move_to([CARD_X, -0.12, 0])
        content.move_to(bg).align_to(bg, LEFT).shift(RIGHT * pad)
        for m in (bg, content):
            m.set_z_index(9)

        extra = [FadeOut(self.counter)] if self.counter is not None else []
        if marks:
            extra += [LaggedStart(*[Create(m[0]) for m in marks], lag_ratio=0.2),
                      LaggedStart(*[FadeIn(m[1], scale=0.5) for m in marks], lag_ratio=0.2)]
        self.play(
            FadeIn(bg, shift=LEFT * 0.35),
            LaggedStart(FadeIn(head, shift=UP * 0.15), FadeIn(title, shift=UP * 0.15), GrowFromEdge(rule, LEFT),
                        *[FadeIn(r, shift=UP * 0.12) for r in rows], lag_ratio=0.12),
            *extra,
            run_time=1.8,
        )
        self.counter = None
