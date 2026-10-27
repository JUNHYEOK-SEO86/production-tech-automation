"""새로 만든 ITEM 기본정보 입력 폼을 엑셀에서 실제로 불러 값이 마스터 셀에 제대로 들어가는지 확인한다.

테스트 중 바뀐 셀은 저장하지 않고 닫기 때문에 마스터 파일은 변하지 않는다.
사용: python selftest_master_item_form.py "<마스터.xlsm>"
"""
import sys
import time
import traceback

import win32com.client as win32

TEST_CODE = '''
Public Function ItemInfoSelfTest() As String
    Dim ws As Worksheet, log As String
    On Error GoTo EH
    Set ws = ThisWorkbook.Worksheets("1.1MASTER")
    Load frmItemInfo
    With frmItemInfo
        log = "init[고객=" & .Txt_Customer.Value & "|품번=" & .Txt_PartNo.Value & "|아이템=" & .Cmb_Item.Value & _
              "|품명후보=" & .Cmb_ItemName.ListCount & "|단계후보=" & .Cmb_Step.ListCount & _
              "|팀후보=" & .Cmb_Team.ListCount & "|담당자후보=" & .Cmb_Name.ListCount & "]"
        .Txt_Customer.Value = "TEST_CUST"
        .Txt_Project.Value = "TST1"
        .Txt_PartNo.Value = "PN-0001"
        .Txt_Rev.Value = "7"
        .Cmb_Item.Value = "차체"
        log = log & " 차체품명후보=" & .Cmb_ItemName.ListCount
        .Cmb_ItemName.Value = "FR C/MBR"
        .Txt_ItemName.Value = "TEST ITEM"
        .Cmb_Step.Value = "P2"
        .Txt_WeldEO.Value = "EO-W"
        .Txt_AsmEO.Value = ""
        .Cmb_Team.Value = "PM팀"
        log = log & " PM팀담당후보=" & .Cmb_Name.ListCount
        .Cmb_Name.Value = "TESTER"
        .Txt_Quote.Value = "QUOTE1"
        If Not .ApplyToSheet(False) Then log = log & " APPLY실패"
    End With
    Unload frmItemInfo
    ItemInfoSelfTest = log
    Exit Function
EH:
    ItemInfoSelfTest = "ERR " & Err.Number & ": " & Err.Description
End Function
'''

EXPECTED = {
    "D4": "TEST_CUST", "D6": "차체", "D8": "TST1", "D10": "PN-0001",
    "G6": "TEST ITEM", "G4": "FR C/MBR", "G8": "EO-W", "G10": "-",
    "I4": "P2", "I6": "7", "I8": "PM팀", "I10": "TESTER",
    "D2": "TST1차종 TEST ITEM 개발 마스터",
}


def main(path):
    xl = win32.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    xl.EnableEvents = False
    xl.AutomationSecurity = 1  # 테스트를 위해 매크로 허용 (EnableEvents=False라 Workbook_Open은 실행 안 됨)
    wb = None
    try:
        t0 = time.time()
        wb = xl.Workbooks.Open(path, 0, False)
        print(f"열기 완료 ({time.time() - t0:.0f}s)")

        ws = wb.Worksheets("1.1MASTER")
        names = [s.Name for s in ws.Shapes]
        print("버튼 존재:", "btn_ITEM정보입력" in names, "| 기존 아이콘 _001 남아있음:", "_001" in names)
        btn = ws.Shapes("btn_ITEM정보입력")
        print("버튼 매크로:", btn.OnAction, "| 위치:", round(btn.Left, 1), round(btn.Top, 1), round(btn.Width, 1), round(btn.Height, 1))

        module = wb.VBProject.VBComponents("Module_ItemInfo").CodeModule
        module.AddFromString(TEST_CODE)
        result = xl.Run(f"'{wb.Name}'!ItemInfoSelfTest")
        print("자체 테스트:", result)

        failures = []
        for addr, expected in EXPECTED.items():
            actual = ws.Range(addr).Value
            ok = str(actual) == expected
            if not ok:
                failures.append((addr, expected, actual))
        quote = wb.Worksheets("1.2견적투자비List").Range("C3").Value
        if quote != "QUOTE1":
            failures.append(("1.2견적투자비List!C3", "QUOTE1", quote))
        print("셀 매핑 검증:", "모두 일치" if not failures else failures)
        return 0 if not failures and not str(result).startswith("ERR") else 2
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        if wb is not None:
            try:
                wb.Close(False)  # 테스트 변경 내용은 저장하지 않는다
            except Exception:
                pass
        xl.Quit()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1]))
