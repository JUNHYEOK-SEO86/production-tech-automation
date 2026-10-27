"""데이터 모델과 JSON 저장/불러오기.

웹 버전(localStorage)의 상태 구조를 그대로 옮겼습니다:
state = {
    "items": { "세미모듈": {processes, ct_status, cad, inputs}, ... },
    "item_order": ["세미모듈", ...],
    "current_item": "세미모듈",
}
"""
import json
import shutil
import uuid
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
DOCS_DIR = DATA_DIR / "docs"
STATE_FILE = DATA_DIR / "pe_ams_state.json"
ENGINE_SEED_FILE = APP_DIR / "engine" / "method_seed.json"  # tools/extract_method_seed.py 로 만든다

DEFAULT_PROCESSES = [
    {"id": "IN-PLT", "name": "제품 자동 취출"},
    {"id": "A05", "name": "제품 센터링"},
    {"id": "A10", "name": "자동 리탭핑"},
    {"id": "A20", "name": "FR/RR BODY MT'G BUSH 압입"},
    {"id": "A30", "name": "LWR STOPPER 압입"},
    {"id": "A40", "name": "FR L/ARM 가체결"},
    {"id": "A50", "name": "FR L/ARM 본체결"},
    {"id": "A60", "name": "DIM'S 전수검사"},
    {"id": "A70", "name": "UNLOAD'G"},
    {"id": "A80", "name": "작업자 검사"},
    {"id": "OUT-PLT", "name": "PLT 적재"},
]

DEFAULT_CT_VALUES = {
    "IN-PLT": ("4.0", "5.5", "3.0"),
    "A05": ("2.5", "4.0", "1.5"),
    "A10": ("3.0", "9.0", "3.2"),
    "A20": ("3.1", "5.0", "2.3"),
    "A30": ("2.0", "6.0", "1.5"),
    "A40": ("3.5", "6.0", "1.5"),
    "A50": ("4.0", "8.0", "2.3"),
    "A60": ("2.0", "4.0", "1.8"),
    "A70": ("3.0", "5.0", "2.0"),
    "A80": ("1.5", "4.0", "1.0"),
    "OUT-PLT": ("3.2", "6.0", "2.0"),
}


def make_ct_items(loading, work, unload):
    return [
        {"label": "로딩", "value": loading},
        {"label": "작업", "value": work},
        {"label": "언로딩", "value": unload},
    ]


def default_item_state():
    return {
        "processes": [dict(p) for p in DEFAULT_PROCESSES],
        "ct_status": [
            {"id": pid, "items": make_ct_items(*vals)}
            for pid, vals in DEFAULT_CT_VALUES.items()
        ],
        "cad": {"image": "", "nodes": []},
        "inputs": {"car": "NX5a", "qty": "200,000", "eff": "90", "hours": "15.34", "days": "240"},
    }


FIXED_VERSION = 3
STEP_REMOVE = {"L1", "L2", "L3", "L4", "PILOT"}
STEP_ADD = ["AP1", "AP2", "SP1", "LP1", "LP2", "M", "SOP"]
OLD_TEAM_RENAME = {"글로벌스트럭쳐팀": "생산기술1팀"}
NEW_TEAM = "생산기술1팀"
DEFAULT_RANKS = ["상무", "책임", "선임", "주임"]
SITES = ["국내", "중국", "인도", "미국", "브라질", "기타"]
HISTORY_ROWS = 6
EFF_CHOICES = [f"{n}%" for n in range(60, 101)]


def default_work_conditions():
    return [{"site": site, "days": "", "hours": "", "eff": ""} for site in SITES]


def default_master_info():
    """MASTER 정보 기입 화면의 입력값 (ITEM 1개 기준)."""
    def history():
        return [{"date": "", "eo": "", "note": ""} for _ in range(HISTORY_ROWS)]

    return {
        "project": {"customer": "", "part_no": "", "item": "", "item_class": "",
                    "car": "", "item_name": "", "step": ""},
        "report": {"team": "", "person": "", "rank": "", "rev": "0"},
        "recent": {"weld_eo": "", "asm_eo": ""},
        "weld_history": history(),
        "asm_history": history(),
        "line_condition": {"qty_man": "", "site": "", "weld_shift": "", "asm_shift": ""},
        "lines": [],
        "work_conditions": default_work_conditions(),
        "processes": [],
    }


def _fill_missing(target, defaults):
    for key, default in defaults.items():
        if key not in target:
            target[key] = default
        elif isinstance(default, dict) and isinstance(target[key], dict):
            _fill_missing(target[key], default)


def default_state():
    return {
        "items": {"세미모듈": default_item_state()},
        "item_order": ["세미모듈"],
        "current_item": "세미모듈",
    }


def parse_number(text):
    try:
        return float(str(text).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def format_with_commas(value):
    text = str(value).replace(",", "").strip()
    if not text:
        return ""
    neg = text.startswith("-")
    if neg:
        text = text[1:]
    if "." in text:
        whole, frac = text.split(".", 1)
    else:
        whole, frac = text, ""
    whole = whole.lstrip("0") or "0"
    try:
        formatted = "{:,}".format(int(whole))
    except ValueError:
        return ("-" if neg else "") + text
    if neg:
        formatted = "-" + formatted
    return formatted + ("." + frac if frac else "")


def required_ct(info):
    """필요 C/T(초/대) = 3600초/시간 x 일 근무시간 x 라인효율 x 연간 근무일수 / 고객 생산대수.

    생산대수는 Line Condition의 생산대(만대)이고, 근무일/근무시간/라인효율은 설치장에 해당하는 근무 조건 행을 쓴다."""
    condition = info["line_condition"]
    control = next((r for r in info["work_conditions"] if r.get("site") and r["site"] == condition.get("site")), None)
    if not control:
        return None
    qty = parse_number(condition.get("qty_man")) * 10000
    days = parse_number(control.get("days"))
    hours = parse_number(control.get("hours"))
    eff = parse_number(str(control.get("eff", "")).replace("%", "")) / 100
    if min(qty, days, hours, eff) <= 0:
        return None
    return 3600 * hours * eff * days / qty


def compute_target_ct(inputs):
    """목표 C/T(초/대) = 연근무일 x 일근무시간 x 3600초 x 라인효율 / 생산대수"""
    qty = parse_number(inputs.get("qty"))
    eff = parse_number(inputs.get("eff")) / 100.0
    hours = parse_number(inputs.get("hours"))
    days = parse_number(inputs.get("days"))
    if qty <= 0:
        return 0.0
    return (days * hours * 3600 * eff) / qty


class AppState:
    def __init__(self):
        self.data = default_state()
        self.load()

    # ---------- 저장/불러오기 ----------
    def load(self):
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if loaded.get("items"):
                    self.data = loaded
                    return
            except (OSError, json.JSONDecodeError) as e:
                print(f"상태 로드 실패: {e}")
        self.data = default_state()

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def export_to(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def import_from(self, path):
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not loaded.get("items"):
            raise ValueError("올바른 백업 파일이 아닙니다.")
        self.data = loaded
        self.data.setdefault("item_order", list(self.data["items"].keys()))
        if self.data.get("current_item") not in self.data["items"]:
            self.data["current_item"] = self.data["item_order"][0]
        self.save()

    # ---------- 접근자 ----------
    @property
    def current_item(self):
        return self.data["current_item"]

    @current_item.setter
    def current_item(self, value):
        self.data["current_item"] = value

    @property
    def item_order(self):
        return self.data["item_order"]

    @property
    def items(self):
        return self.data["items"]

    def current(self):
        return self.items[self.current_item]

    @property
    def fixed_values(self):
        """드롭다운에 쓰는 고정값 {키: [값, ...]}. 처음 한 번만 NameList에서 가져오고 이후에는 앱에서 수정한다."""
        if "fixed_values" not in self.data:
            from app.namelist import load_namelist
            self.data["fixed_values"] = {k: list(v) for k, v in load_namelist().items()}
            self.data["fixed_values_version"] = 1
        version = self.data.get("fixed_values_version", 1)
        if version < FIXED_VERSION:
            if version < 2:
                self._migrate_fixed_values(self.data["fixed_values"])
            self._seed_method_lists(self.data["fixed_values"])
            self.data["fixed_values_version"] = FIXED_VERSION
            self.save()
        return self.data["fixed_values"]

    @staticmethod
    def _seed_method_lists(fv):
        """공법 설계용 목록(JIG 원가, 설비 단가)을 마스터 엑셀에서 뽑아 둔 시드로 처음 한 번 채운다."""
        try:
            with open(ENGINE_SEED_FILE, "r", encoding="utf-8") as f:
                seed = json.load(f)
        except (OSError, ValueError):
            seed = {}
        fv.setdefault("Jig", seed.get("jig", {}))
        for group in ("JIG BASE", "JIG TYPE", "차광막/안전센서", "EJECTOR", "JIG UNIT", "UTILITY"):
            fv["Jig"].setdefault(group, [])
        fv.setdefault("Equip", seed.get("equip", {}))
        fv.setdefault("EquipAllowed", seed.get("equip_allowed", {}))

    @staticmethod
    def _migrate_fixed_values(fv):
        # 단계: L1~L4, PILOT 삭제 후 AP1 ~ SOP 추가
        steps = [v for v in (fv.get("DesStep") or ["T-CAR", "PROTO"]) if v not in STEP_REMOVE]
        steps += [v for v in STEP_ADD if v not in steps]
        fv["DesStep"] = steps
        fv.pop("Step", None)  # 업무 단계는 삭제

        # 팀명: 글로벌스트럭쳐팀 -> 생산기술1팀
        teams = []
        for name in fv.get("Team", []):
            name = OLD_TEAM_RENAME.get(name, name)
            if name not in teams:
                teams.append(name)
        fv["Team"] = teams

        fv.setdefault("Rank", list(DEFAULT_RANKS))
        fv.setdefault("Rev", [str(n) for n in range(31)])

        # 담당자: 소속별 {이름, 직급}. 기존 샤시기술팀 명단은 생산기술1팀 소속으로 옮긴다.
        if "Persons" not in fv:
            fv["Persons"] = {NEW_TEAM: [{"name": n, "rank": ""} for n in fv.get("샤시기술팀_Name", [])]}
        fv.pop("샤시기술팀_Name", None)
        fv.pop("차체기술팀_Name", None)

    def persons(self, team):
        return self.fixed_values.setdefault("Persons", {}).get(team, [])

    def fixed_groups(self, store, defaults):
        """이름을 직접 추가/수정/삭제할 수 있는 '목록 묶음' 정의. [{label, key}, ...]"""
        groups = self.fixed_values.setdefault("_groups", {})
        if store not in groups:
            groups[store] = [{"label": label, "key": key} for label, key in defaults]
            self.save()
        return groups[store]

    def fixed_list(self, key):
        return self.fixed_values.setdefault(key, [])

    def set_fixed_list(self, key, values):
        self.fixed_values[key] = list(values)
        self.save()

    def item_choices(self):
        """상단 ITEM 선택(품명) 목록: 고정값의 모든 품명 + 이미 만들어져 있는 ITEM."""
        names = []
        for item in self.fixed_list("Item"):
            for name in self.fixed_list(f"{item}_품명"):
                if name not in names:
                    names.append(name)
        for name in self.item_order:
            if name not in names:
                names.append(name)
        return names

    def item_class_of(self, part_name):
        """품명이 속한 아이템(샤시/차체 ...). 없으면 빈 문자열."""
        for item in self.fixed_list("Item"):
            if part_name in self.fixed_list(f"{item}_품명"):
                return item
        return ""

    # ---------------- 화면 설정 (입력창/열 너비) ----------------
    def get_width(self, key):
        return self.data.get("ui", {}).get("widths", {}).get(key)

    def set_width(self, key, value):
        widths = self.data.setdefault("ui", {}).setdefault("widths", {})
        if value:
            widths[key] = value
        else:
            widths.pop(key, None)
        self.save()

    def master_info(self):
        """현재 ITEM의 MASTER 정보 (없는 항목은 기본값으로 채워서 돌려준다)."""
        info = self.current().setdefault("master", {})
        if "work_conditions" not in info:  # 예전 line_control {설치장소: {...}} 를 행 목록으로 옮긴다
            old = info.get("line_control")
            if old:
                info["work_conditions"] = [
                    {"site": site, "days": v.get("days", ""), "hours": v.get("hours") or v.get("hours_day", ""),
                     "eff": v.get("eff", "")}
                    for site, v in old.items()
                ]
        info.pop("line_control", None)
        _fill_missing(info, default_master_info())
        if not info.get("history_padded"):  # 예전 데이터를 6칸으로 맞추는 건 처음 한 번만 (이후 삭제한 칸은 되살리지 않는다)
            for key in ("weld_history", "asm_history"):
                while len(info[key]) < HISTORY_ROWS:
                    info[key].append({"date": "", "eo": "", "note": ""})
            info["history_padded"] = True
        return info

    # ---------------- 관리문서(엑셀) ----------------
    @property
    def docs(self):
        return self.data.setdefault("docs", {})

    @property
    def doc_entries(self):
        return self.data.setdefault("doc_entries", [])

    @property
    def line_names(self):
        return self.data.setdefault("line_names", [])

    def add_line_name(self, name):
        name = name.strip()
        if name and name not in self.line_names:
            self.line_names.append(name)
            self.save()

    def doc_dir(self, doc):
        return DOCS_DIR / doc["dir"]

    # ---------- 아이템(라인) 관리 ----------
    def add_item(self, name):
        if not name or name in self.items:
            return False
        state = default_item_state()
        state["processes"] = [{"id": "OP10", "name": "신규 공정"}]
        state["ct_status"] = [{"id": "OP10", "items": make_ct_items("0.0", "0.0", "0.0")}]
        self.items[name] = state
        self.item_order.append(name)
        self.current_item = name
        self.save()
        return True

    def delete_item(self, name):
        if name not in self.items:
            return
        del self.items[name]
        self.item_order.remove(name)
        if self.item_order:
            self.current_item = self.item_order[0]
        self.save()

    # ---------- 이미지 ----------
    def copy_image(self, source_path):
        """업로드한 이미지를 data/images 로 복사하고 저장된 파일명을 반환한다."""
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        source = Path(source_path)
        dest_name = f"{uuid.uuid4().hex}{source.suffix.lower()}"
        dest = IMAGES_DIR / dest_name
        shutil.copyfile(source, dest)
        return dest_name

    def save_qimage(self, image):
        """클립보드 등에서 가져온 QImage 를 data/images 에 PNG로 저장하고 파일명을 반환한다."""
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        dest_name = f"{uuid.uuid4().hex}.png"
        image.save(str(IMAGES_DIR / dest_name), "PNG")
        return dest_name

    def resolve_image(self, filename):
        if not filename:
            return ""
        path = IMAGES_DIR / filename
        return str(path) if path.exists() else ""
