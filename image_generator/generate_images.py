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

MODEL = "gemini-2.5-flash-image"
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
}

CONSISTENCY_PREFIX = "Keep the exact same face and outfit from the reference image(s). "


def parse_args():
    p = argparse.ArgumentParser(description="CSV 프롬프트로 컷 이미지를 일괄 생성합니다.")
    p.add_argument("--csv", default="prompts.csv", help="프롬프트 CSV 파일 경로 (기본: prompts.csv)")
    p.add_argument("--out", default="output_images", help="이미지 저장 폴더 (기본: output_images)")
    p.add_argument("--delay", type=float, default=3.0, help="성공 후 대기 시간(초) (기본: 3)")
    p.add_argument("--retries", type=int, default=3, help="실패 시 재시도 횟수 (기본: 3)")
    p.add_argument("--api-key", default=None, help="API 키 (미지정 시 GEMINI_API_KEY 환경변수 사용)")
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


def generate_image(client, contents, retries):
    """이미지 1장을 생성해 PIL Image로 반환. 실패하면 None."""
    for attempt in range(1, retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
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
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("[오류] API 키가 없습니다. GEMINI_API_KEY 환경변수를 설정하거나 --api-key 옵션을 사용하세요.")
    if not os.path.exists(args.csv):
        sys.exit(f"[오류] CSV 파일을 찾을 수 없습니다: {args.csv}")

    os.makedirs(args.out, exist_ok=True)
    client = genai.Client(api_key=api_key)
    rows = load_rows(args.csv)
    total = len(rows)
    master_images = {}
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

        print(f"[{idx}/{total} 생성 중] {filename} - {scene_desc}")

        # 인물 일관성 유지를 위해 등장 인물의 마스터 이미지 첨부
        contents = []
        if not is_master:
            for name, char_id in CHARACTERS.items():
                if name in scene_desc and char_id in master_images:
                    contents.append(master_images[char_id])
            if contents:
                print(f"    참조 이미지 {len(contents)}장 첨부")
                prompt = CONSISTENCY_PREFIX + prompt
        contents.append(prompt)

        img = generate_image(client, contents, args.retries)
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

    print("\n=== 작업 완료 ===")
    print(f"생성 {ok}장 / 건너뜀 {skipped}장 / 실패 {len(failed)}장 (총 {total}컷)")
    if failed:
        print("실패한 컷 (다시 실행하면 이 컷들만 재시도합니다):")
        for name in failed:
            print(f"  - {name}")
    print(f"결과 폴더: {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
