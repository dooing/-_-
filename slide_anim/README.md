# 스크린샷 단계별 설명 애니메이션 (PPT용)

캡처 이미지를 가지고 **스페이스바를 누를 때마다 한 단계씩 진행되는 슬라이드**를 만드는 도구입니다.
각 단계에서 카메라가 설명할 영역으로 확대, 이동하고, 나머지 화면은 어두워지며 강조 박스와 설명 카드가 나타납니다.
애니메이션이 끝나면 그 장면에서 멈춰 있고, 스페이스바를 누르면 다음 단계 애니메이션이 재생됩니다.

결과물: 단계마다 자동 재생 동영상이 한 장씩 들어간 PowerPoint 파일(.pptx). 슬라이드를 복사해서 기존 발표 자료에 붙여 넣으면 됩니다.

## 파일 구성

* `walkthrough.py`: 애니메이션 엔진 (보통은 수정할 필요 없음)
* `demo_deck.py`: 예제 덱. 복사해서 이미지, 영역, 설명만 바꿔 쓰면 됨
* `pick_region.py`: 캡처 이미지에서 영역을 드래그하면 픽셀 좌표를 알려 주는 도구
* `make_sample_images.py`: 데모용 가짜 스크린샷 2장 생성
* `output/DemoDeck.pptx`: 데모를 렌더링한 PPT

## 설치

Python 3.11 또는 3.12를 권장합니다.

```bash
pip install -r requirements.txt
```

버전을 고정한 이유 (2026년 11월 기준 확인):

* `manim` 0.22는 `manim-slides` 5.7과 맞지 않아 `write_to_movie` 오류가 납니다. 0.21.0을 쓰세요.
* Pillow 12 이상에서는 manim 0.21의 이미지 렌더링이 `Invalid mode for data type` 오류를 냅니다. `pillow<12`를 쓰세요.

LaTeX이나 FFmpeg는 따로 설치하지 않아도 됩니다 (manim이 내장 PyAV를 사용).

## 사용 순서

1. **캡처 준비**: 설명할 화면 이미지를 `images/` 같은 폴더에 넣습니다.

2. **영역 좌표 얻기**: 강조할 영역을 드래그하면 Step에 바로 붙여 넣을 수 있는 형태로 좌표가 출력됩니다.
   ```bash
   python pick_region.py images/my_screen.png
   ```

3. **덱 작성**: `demo_deck.py`를 복사해 `my_deck.py`를 만들고 클래스 이름과 `STEPS`를 고칩니다.
   ```python
   from walkthrough import Step, Walkthrough

   class MyDeck(Walkthrough):
       THEME = "dark"                      # 또는 "light"
       EYEBROW = "METHOD OVERVIEW"         # 표지 제목 위 작은 영문
       TITLE = "새 분석법\n단계별 소개"      # \n 으로 줄바꿈
       SUBTITLE = "표지 부제목"
       HEADER = "왼쪽 위에 표시될 문구"
       STEPS = [
           Step("images/screen1.png", (18, 77, 369, 484), "데이터 불러오기",
                "**두 개의 별표**로 감싸면 강조색 굵은 글씨가 됩니다."),
           Step("images/screen1.png", (387, 77, 1782, 682), "결과 그래프",
                "확대하지 않으려면 zoom=False 를 줍니다.", zoom=False),
       ]
   ```

4. **렌더링** (이 폴더 안에서 실행)
   ```bash
   manim-slides render -ql my_deck.py MyDeck                   # 빠른 확인 (저해상도)
   manim-slides render -qh --frame_rate 30 my_deck.py MyDeck   # 최종 (1080p)
   ```

5. **미리보기**: 스페이스바로 넘기며 확인하는 창이 열립니다.
   ```bash
   manim-slides present MyDeck
   ```

6. **PPT로 변환**
   ```bash
   manim-slides convert --to=pptx MyDeck output/MyDeck.pptx
   ```

## PPT에서 쓰기

* 슬라이드 크기는 표준 16:9 (13.33 x 7.5 in)입니다. 슬라이드를 복사해서 기존 발표 자료에 그대로 붙여 넣으면 됩니다.
* 각 슬라이드에는 해당 단계의 동영상이 자동 재생으로 들어 있습니다. 슬라이드 쇼에서 스페이스바를 누르면 다음 슬라이드로 넘어가며 다음 애니메이션이 재생됩니다.
* 발표자 노트에 각 단계의 설명 문구가 들어 있습니다.

## 설정 항목

덱 (클래스 속성)

* `THEME`: `"dark"` 또는 `"light"`. PPT 배경이 밝으면 `"light"`
* `EYEBROW`, `TITLE`, `SUBTITLE`: 표지 문구
* `HEADER`: 단계 진행 중 왼쪽 위 작은 문구 (기본값은 TITLE)
* `SHOW_RECAP`, `RECAP_TITLE`: 마지막 정리 슬라이드 표시 여부와 제목
* `MOVE_TIME`: 카메라 이동 시간(초, 기본 1.6)
* `MAX_UPSCALE`: 최대 확대 배율 (기본 2.0). 작은 영역이 너무 작게 보이면 올리고, 흐려지면 내립니다
* `FONT`: 글꼴 이름. 비워 두면 설치된 한글 글꼴을 자동 선택 (Pretendard, Noto Sans KR, 맑은 고딕 등)

Step

* `image`: 이미지 경로 (덱 파일 기준 상대 경로)
* `region`: `(x0, y0, x1, y1)`, 이미지 픽셀 좌표 (왼쪽 위가 0, 0)
* `title`, `body`: 카드 제목과 본문. 줄바꿈은 자동이고 `**글자**`는 강조됩니다
* `zoom`: `True`(기본)면 영역을 확대, `False`면 전체 화면을 유지하고 영역만 강조
* `layout`: `"auto"`(기본), `"side"`(카드가 오른쪽), `"bottom"`(카드가 아래). auto는 영역이 더 크게 보이는 배치를 고릅니다
* `notes`: 발표자 노트 (생략하면 title + body)

## 문제 해결

* 한글이 네모로 나온다: `FONT = "Malgun Gothic"`처럼 PC에 설치된 글꼴을 지정하세요.
* 스크린샷이 흐리다: 원본 캡처를 고해상도(모니터 원래 해상도 이상)로 쓰고, `MAX_UPSCALE`을 1.5 정도로 조정하세요.
* 렌더링이 느리다: `-ql`로 배치와 문구를 먼저 확인하고, 마지막에만 `-qh`로 렌더링하세요. 이 데모(7단계)는 1080p30 기준 약 5분 걸렸습니다.
