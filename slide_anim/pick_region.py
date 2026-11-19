"""캡처 이미지에서 강조할 영역을 마우스로 드래그해 픽셀 좌표를 얻는 도구.

실행: python pick_region.py sample_images/analyzer.png
사용: 영역을 드래그하면 Step 에 바로 붙여 넣을 수 있는 (x0, y0, x1, y1) 이 출력된다.
      여러 번 드래그해도 되고, 창을 닫으면 끝난다.
"""
import sys

import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector
from PIL import Image


def main(path):
    img = Image.open(path)
    fig, ax = plt.subplots(figsize=(13, 8))
    ax.imshow(img)
    ax.set_title(f"{path}  ({img.width} x {img.height})  : 영역을 드래그하세요")
    count = [0]

    def on_select(press, release):
        x0, x1 = sorted([press.xdata, release.xdata])
        y0, y1 = sorted([press.ydata, release.ydata])
        count[0] += 1
        box = (round(x0), round(y0), round(x1), round(y1))
        print(f'{count[0]:2d}: Step("{path}", {box}, "제목", "설명"),')
        ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="#4CC9F0", lw=2))
        ax.text(x0, y0, str(count[0]), color="white", backgroundcolor="#4CC9F0", fontsize=10)
        fig.canvas.draw_idle()

    selector = RectangleSelector(ax, on_select, useblit=True, button=[1], interactive=False)
    plt.tight_layout()
    plt.show()
    return selector


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python pick_region.py <이미지 경로>")
        sys.exit(1)
    main(sys.argv[1])
