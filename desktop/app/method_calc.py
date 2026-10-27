"""공법 설계(마스터 1.1MASTER 시트의 C/T ~ 전용설비 금액 산출표) 데이터와 계산.

공정 1개의 공법 내용은 그 공정 dict 의 "method" 에 저장한다. 목록(JIG 원가, 설비 단가)은 고정값에서 가져온다.
"""
import json
import math
import re

from app.state import parse_number

MODE_GENERAL = "general"   # 작업자/ROBOT/기타 시간 + 작업 항목(횟수 x 시간)
MODE_WELD = "weld"         # 대/중/소물 로딩 + 용접길이로 용접시간 산출
MODE_LABELS = {MODE_GENERAL: "일반 (작업자 / ROBOT / 기타 시간)", MODE_WELD: "용접 (대·중·소물 + 용접길이)"}

EQUIP_ROWS = 8
UNIT_ROWS = 8
WORK_ROWS = 4
LOAD_SECONDS = {"big": 7, "mid": 5, "small": 3}   # 대물 / 중물 / 소물 1개당 로딩 시간(초)
LOAD_FIXED = 3                                     # 로딩 고정 시간(초)
HOME_SECONDS = 3.2                                 # 원점복귀 1회당 시간(초)
TACK_SECONDS = 3                                   # 가접 1회당 시간(초)

JIG_GROUPS = ["JIG BASE", "JIG TYPE", "차광막/안전센서", "EJECTOR", "JIG UNIT", "UTILITY"]
# 금액 산출표의 구분 -> (method["jig"] 키, 고정값 목록 이름)
JIG_ROWS = [
    ("JIG BASE", "base", "JIG BASE"),
    ("JIG TYPE", "type", "JIG TYPE"),
    ("차광막 / 안전센서", "shade", "차광막/안전센서"),
    ("EJECTOR 유/무", "ejector", "EJECTOR"),
    ("기타", "etc", "UTILITY"),
]
EQUIP_SEP = " · "


def default_method():
    return {
        "mode": "",
        "image": "", "marks": [],
        "arc_len": "", "spot": "", "pj": "",
        "load": {"worker": "", "robot": "", "etc": ""},
        "unload": {"worker": "", "robot": "", "etc": ""},
        "work": [{"label": "", "count": "", "time": ""} for _ in range(WORK_ROWS)],
        "weld": {
            "big": "", "mid": "", "small": "", "load_etc": "", "unload": "",
            "r1_len": "", "r2_len": "", "speed": "10", "beads": "", "tack": "",
            "turn": "", "turn_sec": "5", "home": "", "extra": "",
        },
        "equip": [{"kind": "", "cat": "", "name": "", "qty": ""} for _ in range(EQUIP_ROWS)],
        "jig": {"base": "", "type": "", "shade": "", "ejector": "", "etc": "",
                "units": [{"name": "", "qty": ""} for _ in range(UNIT_ROWS)]},
    }


def _fill(target, defaults):
    for key, default in defaults.items():
        if key not in target:
            target[key] = json.loads(json.dumps(default))
        elif isinstance(default, dict) and isinstance(target[key], dict):
            _fill(target[key], default)
        elif isinstance(default, list) and isinstance(target[key], list):
            while len(target[key]) < len(default):
                target[key].append(json.loads(json.dumps(default[len(target[key])])))


def get_method(proc):
    """공정의 method 를 돌려준다. 없는 항목은 기본값으로 채운다."""
    method = proc.setdefault("method", {})
    _fill(method, default_method())
    return method


def default_mode(line_kind, code):
    """상세공정명이 '용접'이고 작업자/검사가 아니면 용접형, 그 밖에는 일반형."""
    text = f"{line_kind} {code}"
    if "용접" in code and not any(w in text for w in ("작업자", "검사", "타각")):
        return MODE_WELD
    return MODE_GENERAL


def mode_of(method, line_kind, code):
    return method.get("mode") or default_mode(line_kind, code)


def number(text):
    return parse_number(text)


def fmt(value, digits=1):
    """계산 결과 표시: 정수면 소수점 없이, 아니면 digits 자리까지."""
    if value is None:
        return ""
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.{digits}f}"


def money(value):
    return f"{int(round(value)):,}" if value else ""


# ---------------- C/T ----------------
def weld_time(weld, length_key):
    """엑셀: ROUNDUP(길이/용접속도 + 2*(비드수-1) + 가접*3 + JIG회전*초 + 원점복귀*3.2 + 추가시간)"""
    length = number(weld[length_key])
    speed = number(weld["speed"])
    if length <= 0 or speed <= 0:
        return 0
    total = (length / speed + 2 * max(number(weld["beads"]) - 1, 0) + number(weld["tack"]) * TACK_SECONDS
             + number(weld["turn"]) * number(weld["turn_sec"]) + number(weld["home"]) * HOME_SECONDS
             + number(weld["extra"]))
    return math.ceil(total - 1e-9)


def compute_ct(method, line_kind="", code="", mode=None):
    mode = mode or mode_of(method, line_kind, code)
    result = {"mode": mode}
    if mode == MODE_WELD:
        w = method["weld"]
        raw = (number(w["big"]) * LOAD_SECONDS["big"] + number(w["mid"]) * LOAD_SECONDS["mid"]
               + number(w["small"]) * LOAD_SECONDS["small"] + number(w["load_etc"]) + LOAD_FIXED)
        load = 0 if raw <= 3 else raw
        result["r1"], result["r2"] = weld_time(w, "r1_len"), weld_time(w, "r2_len")
        work = max(result["r1"], result["r2"])
        unload = number(w["unload"])
        result["arc_len"] = number(w["r1_len"]) + number(w["r2_len"])
    else:
        load = sum(number(method["load"][k]) for k in ("worker", "robot", "etc"))
        unload = sum(number(method["unload"][k]) for k in ("worker", "robot", "etc"))
        work = sum(number(row["count"]) * number(row["time"]) for row in method["work"])
        result["rows"] = [number(row["count"]) * number(row["time"]) for row in method["work"]]
    result.update(load=load, work=work, unload=unload, total=load + work + unload)
    return result


# ---------------- 목록 조회 ----------------
def jig_list(fv, group):
    return fv.get("Jig", {}).get(group, [])


def jig_price(fv, group, name):
    return next((number(i["price"]) for i in jig_list(fv, group) if i["name"] == name), 0)


def equip_label(kind, cat):
    return f"{kind}{EQUIP_SEP}{cat}"


def split_equip_label(label):
    kind, _, cat = label.partition(EQUIP_SEP)
    return kind.strip(), cat.strip()


def equip_groups(fv):
    return fv.get("Equip", {})


def equip_categories(fv, kind, line_kind="", code=""):
    """전용/범용 설비 종류 목록. 상세공정명에 정해진 종류가 있으면 그것만(+직접 추가한 종류) 보여준다."""
    cats = [split_equip_label(label)[1] for label in equip_groups(fv) if split_equip_label(label)[0] == kind]
    allowed_map = fv.get("EquipAllowed", {})
    key = process_key(kind, line_kind, code)
    if key in allowed_map:
        known = {c for values in allowed_map.values() for c in values}
        return [c for c in cats if c in allowed_map[key] or c not in known]
    return cats


def process_key(kind, line_kind, code):
    """엑셀 이름정의 이름: 전용_용접_KEY_ASSY_용접 (구분_용접|조립_상세공정명(특수문자는 _))"""
    stage = "조립" if "조립" in line_kind else "용접"
    return f"{kind}_{stage}_" + re.sub(r"[^0-9A-Za-z가-힣]", "_", code)


def equip_items(fv, kind, cat):
    return equip_groups(fv).get(equip_label(kind, cat), [])


def equip_price(fv, kind, cat, name):
    return next((number(i["price"]) for i in equip_items(fv, kind, cat) if i["name"] == name), 0)


# ---------------- 금액 ----------------
def compute_equipment(method, fv):
    rows, total = [], 0
    for row in method["equip"]:
        price = equip_price(fv, row["kind"], row["cat"], row["name"])
        amount = price * number(row["qty"])
        rows.append({"price": price, "amount": amount})
        total += amount
    return {"rows": rows, "total": total}


def equipment_summary(method):
    """엑셀 L21/L22: 설비명(범용) / JIG명(전용) = '설비명 수량대, ...' (괄호 앞부분만)"""
    texts = {"범용": [], "전용": []}
    for row in method["equip"]:
        if row["kind"] in texts and row["name"]:
            short = row["name"].split("(")[0].strip()
            texts[row["kind"]].append(f"{short} {row['qty']}대".replace("  ", " "))
    return ", ".join(texts["범용"]), ", ".join(texts["전용"])


def compute_jig(method, fv):
    jig = method["jig"]
    lines = {}
    for _label, key, group in JIG_ROWS:
        lines[key] = jig_price(fv, group, jig[key]) if jig[key] else 0
    units = []
    for row in jig["units"]:
        price = jig_price(fv, "JIG UNIT", row["name"]) if row["name"] else 0
        units.append({"price": price, "amount": price * number(row["qty"])})
    total = sum(lines.values()) + sum(u["amount"] for u in units)
    return {"lines": lines, "units": units, "total": total}


# ---------------- 이름 변경/삭제 시 공정 데이터 따라가기 ----------------
def _all_methods(state):
    for item in state.items.values():
        for proc in item.get("master", {}).get("processes", []):
            if "method" in proc:
                yield get_method(proc)


def rename_jig_item(state, group, old, new):
    for method in _all_methods(state):
        jig = method["jig"]
        if group == "JIG UNIT":
            for row in jig["units"]:
                if row["name"] == old:
                    row["name"] = new
        else:
            key = next(k for _l, k, g in JIG_ROWS if g == group)
            if jig[key] == old:
                jig[key] = new


def rename_equip_item(state, label, old, new):
    kind, cat = split_equip_label(label)
    for method in _all_methods(state):
        for row in method["equip"]:
            if row["kind"] == kind and row["cat"] == cat and row["name"] == old:
                row["name"] = new


def rename_equip_group(state, old_label, new_label):
    old_kind, old_cat = split_equip_label(old_label)
    new_kind, new_cat = split_equip_label(new_label)
    for method in _all_methods(state):
        for row in method["equip"]:
            if row["kind"] == old_kind and row["cat"] == old_cat:
                row["kind"], row["cat"] = new_kind, new_cat
