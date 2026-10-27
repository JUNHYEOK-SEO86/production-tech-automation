"""문서 생성에 쓰는 고정값(표준정보) 시트를 공정마스터 안에 내장한다.

내장 시트: STD_공정, STD_관리항목, STD_FMEA, 양식맵  (문서생성기.xlsm 에서 복사)
이렇게 하면 마스터 파일 하나에 기본정보 + 고정값이 모두 들어 있고, 마스터에서 고정값을 고치면 다음 문서 생성에 바로 반영된다.
사용: python embed_std_into_master.py "<마스터 사본.xlsm>" "<문서생성기.xlsm>"
"""
import sys
import time
import traceback

import win32com.client as win32

SHEETS = ["STD_공정", "STD_관리항목", "STD_FMEA", "양식맵"]
TAB_COLOR = 0x9D6B2D  # BGR: 파란 계열 (표준정보 시트 구분용)


def main(master_path, source_path):
    xl = win32.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    xl.EnableEvents = False
    xl.AutomationSecurity = 3
    master = source = None
    try:
        t0 = time.time()
        master = xl.Workbooks.Open(master_path, 0, False)
        source = xl.Workbooks.Open(source_path, 0, True)
        print(f"열기 완료 ({time.time() - t0:.0f}s)")

        existing = [ws.Name for ws in master.Worksheets]
        for name in SHEETS:
            if name in existing:
                master.Worksheets(name).Delete()

        for name in SHEETS:
            src = source.Worksheets(name)
            src.Copy(None, master.Worksheets(master.Worksheets.Count))
            copied = master.Worksheets(master.Worksheets.Count)
            copied.Name = name
            copied.Visible = -1
            copied.Tab.Color = TAB_COLOR
            used = copied.UsedRange
            print(f"  내장: {name:12} 범위={used.Address} 행={used.Rows.Count}")

        master.Worksheets("1.1MASTER").Activate()
        master.Save()
        print(f"저장 완료 ({time.time() - t0:.0f}s) | 시트 수: {master.Worksheets.Count}")
        return 0
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        for wb in (source, master):
            if wb is not None:
                try:
                    wb.Close(False)
                except Exception:
                    pass
        xl.Quit()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1], sys.argv[2]))
