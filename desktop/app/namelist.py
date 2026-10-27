"""마스터 NameList 시트의 선택 목록(아이템, 품명, 팀, 담당자, 공정Code 등).

engine/namelist.json 이 있으면 그것을 쓰고, 없으면 기본 목록만 쓴다. 목록에 없는 값도 직접 입력할 수 있다.
"""
import json
from functools import lru_cache

from app.apqp_bridge import ENGINE_DIR

DEFAULTS = {
    "Item": ["샤시", "차체", "의장", "기타"],
    "Line": ["MAIN용접", "SUB용접", "조립"],
    "설치장소": ["국내", "중국", "인도", "미국", "브라질", "기타"],
    "Shift": ["주간", "야간", "주/야간"],
}


@lru_cache(maxsize=1)
def load_namelist():
    data = {}
    try:
        with open(ENGINE_DIR / "namelist.json", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        pass
    for key, values in DEFAULTS.items():
        if not data.get(key):
            data[key] = list(values)
    return data
