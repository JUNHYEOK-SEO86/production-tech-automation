# PE-AMS Desktop (Python / PySide6)

웹 버전(`../index.html`)을 대체하는 파이썬 데스크톱 GUI입니다. 지금은 앱 골격(사이드바, 아이템 탭, 데이터 저장/백업)과
**1-1. 목표 C/T & 공정 수립** 화면만 구현되어 있습니다. 1-2 / 2번 화면과 엑셀·PPT 연동은 다음 단계에서 추가합니다.

## 실행 방법

```bash
cd desktop
pip install -r requirements.txt
python main.py
```

## 데이터 저장 위치

`desktop/data/pe_ams_state.json` 에 자동 저장됩니다. 업로드한 레이아웃 이미지는 `desktop/data/images/`에 복사되어 보관됩니다.

## 폴더 구조

```
desktop/
  main.py                 앱 진입점
  app/
    state.py              데이터 모델 + JSON 저장/불러오기
    main_window.py         메인 윈도우 (사이드바 + 아이템 탭 + 화면 전환)
    sidebar.py              좌측 메뉴
    item_tabs.py            라인/ITEM 탭 바
    screens/
      screen_master.py       1-1 MASTER 정보 기입 (I. 프로젝트 / II. 라인 / III. 공정)
      screen_ct.py           1-2 목표 C/T & 공정 수립
      screen_docs.py         1-4 관리문서 작성
    widgets/
      cad_layout.py         드래그 가능한 공정 레이아웃 캔버스
      process_table.py       ITEM 및 공정 구성 표
      ct_status_table.py     공정별 C/T 현황 표 (행별 세부 항목 인라인 추가/삭제)
```
