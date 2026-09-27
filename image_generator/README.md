# 나노바나나 컷 이미지 자동 생성기

대본 CSV(`prompts.csv`)를 읽어 **Gemini 나노바나나**로 컷마다 16:9 이미지를 만들고
`output_images/` 폴더에 자동 저장합니다.

## 처음 한 번만 준비

1. **Python 설치**: https://www.python.org (Windows는 설치 시 "Add python.exe to PATH" 체크)
2. **API 키 발급**: https://aistudio.google.com/apikey → *Create API key* (`AIza…`로 시작)

## 실행

- **Windows**: `실행하기.bat` 더블클릭
- **Mac/Linux**: 터미널에서 `./run.sh`

처음 실행하면 API 키를 물어봅니다. `y`를 누르면 `api_key.txt`에 저장되어 다음부터는 묻지 않습니다.
(`api_key.txt`는 저장소에 올라가지 않도록 제외되어 있습니다. 다른 사람과 공유하지 마세요.)

## 동작 방식

- `CHAR_01~04`(캐릭터 마스터 컷)를 먼저 만들고, 이후 장면 설명에 `선옥`/`서연`/`송헌`/`태준`/`서우`가
  나오면 해당 마스터 이미지를 참조로 함께 보내 **얼굴·의상 일관성**을 유지합니다. → CSV에서 CHAR_ 행은 맨 위에.
- 회상 장면(`회상`/`젊은`/`과거`/`30년 전`/`27세` 포함)은 얼굴 특징만 참고하고 나이·의상은 프롬프트대로 그립니다.
- 파일명: `{순번}_{구분}_{컷번호}.png` (예: `05_Chapter1_Cut01.png`)
- **이미 만든 파일은 건너뜁니다.** 중간에 멈추거나 실패해도 다시 실행하면 남은 컷만 이어서 생성합니다.
  특정 컷을 다시 만들고 싶으면 그 파일만 지우고 다시 실행하세요.
- 실패 시 자동 재시도(기본 3회), 끝나면 생성/건너뜀/실패 요약을 보여줍니다.

## 옵션

```bash
python generate_images.py --dry-run                            # API 호출 없이 계획만 확인
python generate_images.py --model gemini-3-pro-image-preview   # 나노바나나 Pro 사용
python generate_images.py --csv 다른대본.csv --out 폴더이름
python generate_images.py --delay 5 --retries 5                # 대기 시간·재시도 횟수
```

API 키는 `GEMINI_API_KEY` 환경변수나 `--api-key` 옵션으로도 지정할 수 있습니다.

## CSV 형식

필수 컬럼: `구분`, `컷 번호`, `대본 매칭 장면`, `나노바나나 프롬프트 (영문 - 16:9 시네마틱 최적화)`
(다른 컬럼은 있어도 무시합니다.) 인물을 추가하려면 `generate_images.py`의 `CHARACTERS`에 `"이름": "CHAR_05"`를 넣으세요.
