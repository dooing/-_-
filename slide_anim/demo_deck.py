"""데모 덱: 이 파일을 복사해서 이미지 경로, 영역 좌표, 설명만 바꿔 쓰면 된다.

렌더링 (이 폴더에서 실행):
    manim-slides render -qh demo_deck.py DemoDeck
미리보기 (스페이스바로 진행):
    manim-slides present DemoDeck
PowerPoint 로 변환:
    manim-slides convert --to=pptx DemoDeck output/DemoDeck.pptx
"""
from walkthrough import Step, Walkthrough

A = "sample_images/analyzer.png"
M = "sample_images/model_report.png"


class DemoDeck(Walkthrough):
    THEME = "dark"  # "dark" 또는 "light"
    EYEBROW = "AI ANALYSIS WORKFLOW"
    TITLE = "라만 스펙트럼 기반\nAI 분류 분석 절차"
    SUBTITLE = "데이터 입력부터 모델 해석까지, 화면을 따라 단계별로 살펴봅니다."
    HEADER = "AI 분류 분석 절차"

    # region = (x0, y0, x1, y1): 캡처 이미지의 픽셀 좌표 (왼쪽 위가 0, 0)
    # 좌표는 pick_region.py 로 드래그해서 얻을 수 있다.
    STEPS = [
        Step(A, (18, 77, 369, 484), "데이터 불러오기",
             "측정한 스펙트럼 파일을 불러오면 **자동 품질 검사**를 거쳐 목록에 표시됩니다. "
             "검사가 필요한 파일은 주황색으로 구분됩니다."),
        Step(A, (18, 500, 369, 1034), "전처리 설정",
             "베이스라인 보정(ALS), 스무딩, 정규화(SNV)를 순서대로 적용해 "
             "**장비와 시료 간 편차**를 줄입니다."),
        Step(A, (387, 77, 1782, 682), "피크 검출",
             "전처리된 스펙트럼(파란색)에서 **주요 피크를 자동으로 검출**합니다. "
             "빨간 표시가 검출된 피크 위치입니다."),
        Step(A, (387, 698, 1782, 1034), "결과 테이블",
             "각 피크의 위치, 강도, 면적과 **할당 성분**을 표로 정리해 바로 내보낼 수 있습니다."),
        Step(M, (18, 77, 1782, 253), "모델 성능 요약",
             "테스트셋 기준 정확도 **0.962**, AUC **0.988**로 세 클래스를 안정적으로 구분합니다."),
        Step(M, (909, 270, 1782, 671), "혼동 행렬",
             "오분류는 주로 **Class B**에서 발생합니다. 유사한 스펙트럼 패턴을 가진 시료를 "
             "추가로 확보하면 개선할 수 있습니다."),
        Step(M, (18, 688, 1782, 1034), "중요 파장 영역",
             "모델이 판단에 주로 사용한 영역은 **1004 cm⁻¹**와 **1450 cm⁻¹** 부근으로, "
             "알려진 성분 피크와 일치합니다."),
    ]
    RECAP_TITLE = "분석 절차 정리"
