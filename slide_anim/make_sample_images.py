"""데모용 가짜 스크린샷 2장을 만든다 (실제 사용 시에는 본인 캡처 이미지를 쓰면 된다).

실행: python make_sample_images.py
결과: sample_images/analyzer.png, sample_images/model_report.png
      각 이미지의 주요 영역 픽셀 좌표를 화면에 출력한다.
"""
from pathlib import Path

import logging

import matplotlib

matplotlib.use("Agg")
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch, Rectangle

OUT = Path(__file__).parent / "sample_images"
OUT.mkdir(exist_ok=True)

W, H, DPI = 1800, 1100, 100
plt.rcParams["font.family"] = ["Noto Sans CJK KR", "Malgun Gothic", "AppleGothic", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

UI_BG = "#F3F5F9"
PANEL = "#FFFFFF"
LINE = "#D9DEE7"
TEXT = "#1F2937"
MUTED = "#6B7280"
BLUE = "#2563EB"


def px_box(x0, y0, x1, y1):
    """figure 좌표(0~1, 아래가 0) 박스를 이미지 픽셀 좌표(왼쪽 위가 0)로 변환."""
    return (round(x0 * W), round((1 - y1) * H), round(x1 * W), round((1 - y0) * H))


def panel(fig, x0, y0, x1, y1, title=None):
    fig.patches.append(
        FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0,rounding_size=0.006",
                       transform=fig.transFigure, facecolor=PANEL, edgecolor=LINE, linewidth=1.2,
                       zorder=-10)
    )
    if title:
        fig.text(x0 + 0.012, y1 - 0.03, title, fontsize=13, fontweight="bold", color=TEXT)
    return px_box(x0, y0, x1, y1)


def toolbar(fig, app_name, menus):
    fig.patches.append(Rectangle((0, 0.945), 1, 0.055, transform=fig.transFigure,
                                 facecolor="#FFFFFF", edgecolor=LINE))
    fig.text(0.012, 0.965, app_name, fontsize=14, fontweight="bold", color=BLUE)
    x = 0.16
    for m in menus:
        fig.text(x, 0.965, m, fontsize=12, color=TEXT)
        x += 0.055
    for i, b in enumerate(["실행", "내보내기"]):
        bx = 0.86 + i * 0.065
        fig.patches.append(FancyBboxPatch((bx, 0.953), 0.055, 0.034, boxstyle="round,pad=0,rounding_size=0.004",
                                          transform=fig.transFigure,
                                          facecolor=BLUE if i == 0 else "#FFFFFF", edgecolor=BLUE))
        fig.text(bx + 0.0275, 0.97, b, fontsize=11, ha="center", va="center",
                 color="white" if i == 0 else BLUE)


def analyzer():
    rng = np.random.default_rng(3)
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=UI_BG)
    toolbar(fig, "Spectra Analyzer", ["파일", "보기", "분석", "도구", "도움말"])
    regions = {}

    # 왼쪽: 데이터셋 목록
    regions["dataset"] = panel(fig, 0.01, 0.56, 0.205, 0.93, "데이터셋")
    files = ["sample_A01.csv", "sample_A02.csv", "sample_B01.csv", "sample_B02.csv", "sample_C01.csv", "blank_01.csv"]
    for i, f in enumerate(files):
        y = 0.86 - i * 0.045
        sel = i == 1
        if sel:
            fig.patches.append(Rectangle((0.016, y - 0.012), 0.183, 0.036, transform=fig.transFigure,
                                         facecolor="#E8EFFE", edgecolor="none"))
        fig.text(0.024, y, ("● " if i < 5 else "○ ") + f, fontsize=11.5, color=BLUE if sel else TEXT)
        fig.text(0.19, y, "OK" if i < 5 else "검사", fontsize=10, ha="right",
                 color="#16A34A" if i < 5 else "#D97706")

    # 왼쪽: 전처리 설정
    regions["preprocess"] = panel(fig, 0.01, 0.06, 0.205, 0.545, "전처리 설정")
    params = [("베이스라인 보정", "ALS (λ=1e5)"), ("스무딩", "Savitzky-Golay"), ("창 크기", "11"),
              ("정규화", "SNV"), ("미분", "1차"), ("범위", "400~1800 cm⁻¹")]
    for i, (k, v) in enumerate(params):
        y = 0.47 - i * 0.062
        fig.text(0.022, y, k, fontsize=11, color=MUTED)
        fig.patches.append(FancyBboxPatch((0.022, y - 0.035), 0.17, 0.028, boxstyle="round,pad=0,rounding_size=0.003",
                                          transform=fig.transFigure, facecolor="#F8FAFC", edgecolor=LINE))
        fig.text(0.03, y - 0.022, v, fontsize=11, color=TEXT)

    # 가운데: 스펙트럼 그래프
    regions["spectrum"] = panel(fig, 0.215, 0.38, 0.99, 0.93, "스펙트럼 (처리 전 / 후)")
    ax = fig.add_axes([0.25, 0.44, 0.72, 0.43])
    x = np.linspace(400, 1800, 1400)
    peaks = [(620, 18, 0.55), (860, 14, 0.9), (1004, 9, 1.4), (1160, 20, 0.6), (1450, 16, 0.95), (1660, 22, 0.75)]
    clean = sum(a * np.exp(-((x - c) / w) ** 2) for c, w, a in peaks)
    raw = clean + 0.6 + 0.0004 * (x - 400) + rng.normal(0, 0.05, x.size)
    ax.plot(x, raw, color="#B6BDC9", lw=1, label="원본")
    ax.plot(x, clean, color=BLUE, lw=1.8, label="전처리 후")
    for c, w, a in peaks:
        ax.plot(c, a + 0.08, marker="v", color="#DC2626", ms=8)
    ax.set_xlabel("Raman shift (cm⁻¹)", color=MUTED)
    ax.set_ylabel("Intensity (a.u.)", color=MUTED)
    ax.tick_params(colors=MUTED)
    for s in ax.spines.values():
        s.set_color(LINE)
    ax.legend(frameon=False, loc="upper left")
    ax.set_xlim(400, 1800)

    # 아래: 피크 테이블
    regions["table"] = panel(fig, 0.215, 0.06, 0.99, 0.365, "검출된 피크")
    cols = ["No.", "위치 (cm⁻¹)", "강도", "면적", "할당 성분"]
    cx = [0.235, 0.32, 0.45, 0.56, 0.68]
    names = ["C-C 신축", "C-O-C 대칭", "페닐 고리", "C-N 신축", "CH₂ 굽힘", "Amide I"]
    for c, xx in zip(cols, cx):
        fig.text(xx, 0.3, c, fontsize=11, fontweight="bold", color=MUTED)
    for i, (c, w, a) in enumerate(peaks[:5]):
        y = 0.26 - i * 0.038
        vals = [f"{i + 1}", f"{c:.0f}", f"{a:.2f}", f"{a * w * 1.77:.1f}", names[i]]
        for v, xx in zip(vals, cx):
            fig.text(xx, y, v, fontsize=11, color=TEXT)

    fig.text(0.012, 0.018, "준비됨  |  6개 파일  |  전처리 완료", fontsize=10, color=MUTED)
    fig.savefig(OUT / "analyzer.png", dpi=DPI, facecolor=UI_BG)
    plt.close(fig)
    return regions


def model_report():
    rng = np.random.default_rng(7)
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=UI_BG)
    toolbar(fig, "Model Report", ["요약", "학습", "평가", "해석", "설정"])
    regions = {}

    # 위: 성능 지표 카드
    metrics = [("정확도", "0.962"), ("F1 점수", "0.951"), ("AUC", "0.988"), ("추론 시간", "12 ms")]
    x0s = [0.01 + i * 0.2475 for i in range(4)]
    for (k, v), x0 in zip(metrics, x0s):
        panel(fig, x0, 0.77, x0 + 0.2375, 0.93)
        fig.text(x0 + 0.015, 0.885, k, fontsize=12, color=MUTED)
        fig.text(x0 + 0.015, 0.8, v, fontsize=30, fontweight="bold", color=TEXT)
    regions["metrics"] = px_box(0.01, 0.77, 0.99, 0.93)

    # 왼쪽: 학습 곡선
    regions["loss"] = panel(fig, 0.01, 0.39, 0.495, 0.755, "학습 곡선")
    ax = fig.add_axes([0.05, 0.44, 0.43, 0.26])
    ep = np.arange(1, 61)
    tr = 1.2 * np.exp(-ep / 12) + 0.08 + rng.normal(0, 0.01, ep.size)
    va = 1.25 * np.exp(-ep / 13) + 0.12 + rng.normal(0, 0.015, ep.size)
    ax.plot(ep, tr, color=BLUE, lw=2, label="train")
    ax.plot(ep, va, color="#F59E0B", lw=2, label="validation")
    ax.legend(frameon=False)
    ax.set_xlabel("Epoch", color=MUTED)
    ax.tick_params(colors=MUTED)
    for s in ax.spines.values():
        s.set_color(LINE)

    # 오른쪽: 혼동 행렬
    regions["confusion"] = panel(fig, 0.505, 0.39, 0.99, 0.755, "혼동 행렬 (테스트셋)")
    ax = fig.add_axes([0.62, 0.45, 0.26, 0.26])
    cm = np.array([[48, 1, 1], [2, 45, 3], [0, 2, 48]])
    ax.imshow(cm, cmap="Blues")
    labels = ["Class A", "Class B", "Class C"]
    ax.set_xticks(range(3), labels)
    ax.set_yticks(range(3), labels)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=14,
                    color="white" if cm[i, j] > 30 else TEXT)
    ax.set_xlabel("예측", color=MUTED)
    ax.set_ylabel("실제", color=MUTED)

    # 아래: 특징 중요도
    regions["importance"] = panel(fig, 0.01, 0.06, 0.99, 0.375, "중요 파장 영역 (특징 기여도)")
    ax = fig.add_axes([0.05, 0.12, 0.92, 0.2])
    x = np.linspace(400, 1800, 140)
    imp = (np.exp(-((x - 1004) / 30) ** 2) + 0.7 * np.exp(-((x - 1450) / 40) ** 2)
           + 0.45 * np.exp(-((x - 860) / 30) ** 2) + rng.uniform(0, 0.06, x.size))
    colors = [BLUE if v > 0.4 else "#BFCDEB" for v in imp]
    ax.bar(x, imp, width=9, color=colors)
    ax.set_xlim(400, 1800)
    ax.set_xlabel("Raman shift (cm⁻¹)", color=MUTED)
    ax.tick_params(colors=MUTED)
    for s in ax.spines.values():
        s.set_color(LINE)

    fig.savefig(OUT / "model_report.png", dpi=DPI, facecolor=UI_BG)
    plt.close(fig)
    return regions


if __name__ == "__main__":
    for name, fn in [("analyzer.png", analyzer), ("model_report.png", model_report)]:
        print(name)
        for k, v in fn().items():
            print(f"  {k:12s} {v}")
