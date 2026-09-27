"""
나노바나나(Gemini 2.5 Flash Image) 일괄 컷 이미지 생성기

prompts.csv 에 적힌 컷별 프롬프트를 읽어 16:9 이미지를 순서대로 생성합니다.
- CHAR_ 로 시작하는 컷(캐릭터 마스터 컷)을 먼저 만들고,
- 본편 장면에서는 대본에 등장하는 인물의 마스터 이미지를 함께 첨부해 얼굴/의상 일관성을 유지합니다.
- 이미 생성된 파일은 건너뛰므로 중간에 멈춰도 다시 실행하면 이어서 진행됩니다.

사용법:
    pip install -r requirements.txt
    export GEMINI_API_KEY="발급받은_API_키"        # Windows: set GEMINI_API_KEY=...
    python generate_images.py
    python generate_images.py --csv my_prompts.csv --out my_images --delay 5
    python generate_images.py --dry-run          # API 호출 없이 계획만 확인
"""

import argparse
import csv
import os
import sys
import time
from io import BytesIO

from PIL import Image
from google import genai
from google.genai import types

MODEL = "gemini-2.5-flash-image"  # 나노바나나. 나노바나나 Pro 사용 시 --model gemini-3-pro-image-preview
KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_key.txt")
ASPECT_RATIO = "16:9"

# CSV 컬럼 이름
COL_CHAPTER = "구분"
COL_CUT = "컷 번호"
COL_SCENE = "대본 매칭 장면"
COL_PROMPT = "나노바나나 프롬프트 (영문 - 16:9 시네마틱 최적화)"

# 장면 설명에 이 이름이 나오면 해당 마스터 컷 이미지를 참조로 첨부
CHARACTERS = {
    "선옥": "CHAR_01",
    "서연": "CHAR_02",
    "송헌": "CHAR_03",
    "태준": "CHAR_04",
    "서우": "CHAR_04",
}

CONSISTENCY_PREFIX = "Keep the exact same face and outfit from the reference image(s). "
# 회상(젊은 시절) 장면은 나이·의상이 다르므로 얼굴 특징만 참고하도록 지시
FLASHBACK_KEYWORDS = ("회상", "젊은", "과거", "30년 전", "27세")
FLASHBACK_PREFIX = (
    "Use the reference image(s) only for facial features and identity; "
    "depict the person at the younger age and in the clothing described below. "
)


def parse_args():
    p = argparse.ArgumentParser(description="CSV 프롬프트로 컷 이미지를 일괄 생성합니다.")
    p.add_argument("--csv", default="prompts.csv", help="프롬프트 CSV 파일 경로 (기본: prompts.csv)")
    p.add_argument("--out", default="output_images", help="이미지 저장 폴더 (기본: output_images)")
    p.add_argument("--delay", type=float, default=3.0, help="성공 후 대기 시간(초) (기본: 3)")
    p.add_argument("--retries", type=int, default=3, help="실패 시 재시도 횟수 (기본: 3)")
    p.add_argument("--api-key", default=None, help="API 키 (미지정 시 GEMINI_API_KEY 환경변수 사용)")
    p.add_argument("--model", default=MODEL, help=f"이미지 모델 (기본: {MODEL})")
    p.add_argument("--dry-run", action="store_true", help="API 호출 없이 파일명/참조 이미지 계획만 출력")
    return p.parse_args()


def clean(text):
    return (text or "").replace(" ", "").replace("[", "").replace("]", "")


def load_rows(csv_path):
    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = {COL_CHAPTER, COL_CUT, COL_SCENE, COL_PROMPT} - set(reader.fieldnames or [])
        if missing:
            sys.exit(f"[오류] CSV에 필요한 컬럼이 없습니다: {', '.join(sorted(missing))}")
        return [row for row in reader if (row.get(COL_PROMPT) or "").strip()]


def get_api_key(cli_key):
    """API 키 우선순위: --api-key > 환경변수 > api_key.txt > 직접 입력(입력 시 api_key.txt에 저장)."""
    key = cli_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key.strip()
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8") as f:
            key = f.read().strip()
        if key:
            return key
    if not sys.stdin.isatty():
        return None
    import getpass
    key = getpass.getpass("Gemini API 키를 입력하세요 (화면에 표시되지 않음): ").strip()
    if key and input("다음에도 쓰도록 api_key.txt에 저장할까요? (y/N): ").strip().lower() == "y":
        with open(KEY_FILE, "w", encoding="utf-8") as f:
            f.write(key)
        print(f"  -> 저장됨: {KEY_FILE} (다른 사람과 공유하지 마세요)")
    return key or None


def generate_image(client, model, contents, retries):
    """이미지 1장을 생성해 PIL Image로 반환. 실패하면 None."""
    for attempt in range(1, retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio=ASPECT_RATIO),
                ),
            )
            for candidate in response.candidates or []:
                for part in (candidate.content.parts if candidate.content else None) or []:
                    if part.inline_data and part.inline_data.data:
                        img = Image.open(BytesIO(part.inline_data.data))
                        img.load()
                        return img
            print(f"    -> 응답에 이미지가 없습니다 (시도 {attempt}/{retries})")
        except Exception as e:
            print(f"    -> [오류] {e} (시도 {attempt}/{retries})")
        if attempt < retries:
            time.sleep(5 * attempt)  # 점점 길게 대기
    return None


def main():
    args = parse_args()
    api_key = None if args.dry_run else get_api_key(args.api_key)
    if not api_key and not args.dry_run:
        sys.exit("[오류] API 키가 없습니다. GEMINI_API_KEY 환경변수, api_key.txt 파일, --api-key 옵션 중 하나로 지정하세요.")
    if not os.path.exists(args.csv):
        sys.exit(f"[오류] CSV 파일을 찾을 수 없습니다: {args.csv}")

    if not args.dry_run:
        os.makedirs(args.out, exist_ok=True)
    client = None if args.dry_run else genai.Client(api_key=api_key)
    rows = load_rows(args.csv)
    total = len(rows)
    master_images = {}
    planned_masters = set()  # dry-run 에서 생성 예정인 마스터 컷
    ok, skipped, failed = 0, 0, []

    for idx, row in enumerate(rows, start=1):
        chapter = clean(row[COL_CHAPTER])
        cut_no = clean(row[COL_CUT])
        scene_desc = row[COL_SCENE] or ""
        prompt = row[COL_PROMPT].strip()
        is_master = cut_no.startswith("CHAR_")

        filename = f"{idx:02d}_{chapter}_{cut_no}.png"
        filepath = os.path.join(args.out, filename)

        # 이미 만들어진 파일은 건너뛰기 (마스터 컷은 참조용으로 메모리에 로드)
        if os.path.exists(filepath):
            print(f"[{idx}/{total} 건너뜀] 이미 존재함: {filename}")
            if is_master:
                with Image.open(filepath) as im:
                    master_images[cut_no] = im.copy()
            skipped += 1
            continue

        print(f"[{idx}/{total} {'생성 예정' if args.dry_run else '생성 중'}] {filename} - {scene_desc}")

        # 인물 일관성 유지를 위해 등장 인물의 마스터 이미지 첨부
        contents = []
        if not is_master:
            ref_ids = []
            for name, char_id in CHARACTERS.items():
                if name in scene_desc and char_id not in ref_ids:
                    ref_ids.append(char_id)
            if args.dry_run:
                ref_ids = [c for c in ref_ids if c in master_images or c in planned_masters]
            else:
                ref_ids = [c for c in ref_ids if c in master_images]
            is_flashback = any(k in scene_desc for k in FLASHBACK_KEYWORDS)
            if ref_ids:
                print(f"    참조 이미지: {', '.join(ref_ids)}" + (" (회상 장면: 얼굴만 참고)" if is_flashback else ""))
                prompt = (FLASHBACK_PREFIX if is_flashback else CONSISTENCY_PREFIX) + prompt
                contents.extend(master_images[c] for c in ref_ids if c in master_images)

        if args.dry_run:
            if is_master:
                planned_masters.add(cut_no)
            ok += 1
            continue
        contents.append(prompt)

        img = generate_image(client, args.model, contents, args.retries)
        if img is None:
            print(f"    -> [실패] {filename}")
            failed.append(filename)
            continue

        img.save(filepath)
        print(f"    -> 저장 성공: {filepath}")
        if is_master:
            master_images[cut_no] = img
        ok += 1
        time.sleep(args.delay)  # 서버 과부하 방지

    if args.dry_run:
        print(f"\n=== 드라이런 완료: 생성 예정 {ok}컷 / 이미 존재 {skipped}컷 (총 {total}컷) ===")
        return

    print("\n=== 작업 완료 ===")
    print(f"생성 {ok}장 / 건너뜀 {skipped}장 / 실패 {len(failed)}장 (총 {total}컷)")
    if failed:
        print("실패한 컷 (다시 실행하면 이 컷들만 재시도합니다):")
        for name in failed:
            print(f"  - {name}")
    print(f"결과 폴더: {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
