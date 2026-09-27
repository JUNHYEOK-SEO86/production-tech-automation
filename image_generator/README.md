# 컷 이미지 일괄 생성기 (Gemini 2.5 Flash Image)

`prompts.csv`의 컷별 프롬프트로 16:9 이미지를 순서대로 생성합니다.

- `CHAR_`로 시작하는 컷은 캐릭터 마스터 이미지로 저장되며, 이후 장면 설명에
  `선옥`/`서연`/`송헌`이 나오면 해당 마스터 이미지를 참조로 첨부해 얼굴·의상 일관성을 유지합니다.
  → CSV에서 **CHAR_ 행을 맨 위에** 두세요.
- 이미 생성된 파일은 건너뛰므로, 중단되거나 실패한 컷은 다시 실행하면 이어서 생성됩니다.
- 실패 시 자동 재시도(기본 3회)하고, 마지막에 생성/건너뜀/실패 요약을 출력합니다.

## 사용법

```bash
pip install -r requirements.txt

# API 키는 코드에 적지 말고 환경변수로 지정
export GEMINI_API_KEY="발급받은_API_키"      # Windows(cmd): set GEMINI_API_KEY=발급받은_API_키

python generate_images.py                   # prompts.csv → output_images/
python generate_images.py --csv my.csv --out imgs --delay 5 --retries 5
```

## CSV 형식

필수 컬럼: `구분`, `컷 번호`, `대본 매칭 장면`, `나노바나나 프롬프트 (영문 - 16:9 시네마틱 최적화)`
예시는 `prompts.sample.csv` 참고. 파일명은 `{순번}_{구분}_{컷번호}.png` 형식으로 저장됩니다.

인물 추가는 `generate_images.py`의 `CHARACTERS` 딕셔너리에 `"이름": "CHAR_04"` 형태로 넣으면 됩니다.
