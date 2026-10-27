"""공정마스터(.xlsm) 복사본에 'ITEM 기본정보 입력' 폼/버튼을 만들고 기존 입력 아이콘을 지운다.

사전 조건: 엑셀 보안 센터에서 'VBA 프로젝트 개체 모델에 안전하게 액세스할 수 있음'이 켜져 있어야 한다.
사용: python build_master_item_form.py "<마스터 사본.xlsm>"   (원본이 아닌 사본 경로를 줄 것)
"""
import sys
import time
import traceback

import win32com.client as win32

SHEET = "1.1MASTER"
FORM_NAME = "frmItemInfo"
MODULE_NAME = "Module_ItemInfo"
OLD_ICON = "_001"
NEW_BUTTON = "btn_ITEM정보입력"
FONT = "맑은 고딕"


def rgb(r, g, b):
    return r + g * 256 + b * 65536


C_BG = rgb(241, 245, 249)
C_BANNER = rgb(17, 24, 39)
C_SUB = rgb(148, 163, 184)
C_BLUE = rgb(37, 99, 235)
C_LABEL = rgb(71, 85, 105)
C_LINE = rgb(203, 213, 225)
C_WHITE = rgb(255, 255, 255)
C_INK = rgb(15, 23, 42)
C_CANCEL = rgb(226, 232, 240)

MODULE_CODE = '''Option Explicit

Public Sub ITEM정보입력()
    On Error GoTo EH
    ThisWorkbook.Worksheets("1.1MASTER").Activate
    frmItemInfo.Show vbModal
    Exit Sub
EH:
    MsgBox "ITEM 기본정보 입력창을 열 수 없습니다." & vbCrLf & Err.Description, vbExclamation, "ITEM 기본정보"
End Sub
'''

FORM_CODE = '''Option Explicit

Private Const SHEET_MASTER As String = "1.1MASTER"
Private Const SHEET_QUOTE As String = "1.2견적투자비List"
Private mLoading As Boolean

Private Sub UserForm_Initialize()
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Worksheets(SHEET_MASTER)
    mLoading = True

    FillCombo Cmb_Item, "Item"
    FillCombo Cmb_Step, "DesStep"
    FillCombo Cmb_Team, "Team"

    Txt_Customer.Value = CStr(ws.Range("D4").Value)
    Txt_Project.Value = CStr(ws.Range("D8").Value)
    Txt_PartNo.Value = CStr(ws.Range("D10").Value)
    Txt_Rev.Value = CStr(ws.Range("I6").Value)
    Cmb_Item.Value = CStr(ws.Range("D6").Value)
    RefreshItemNames
    Cmb_ItemName.Value = CStr(ws.Range("G4").Value)
    Txt_ItemName.Value = CStr(ws.Range("G6").Value)
    Cmb_Step.Value = CStr(ws.Range("I4").Value)
    Txt_WeldEO.Value = CleanDash(ws.Range("G8").Value)
    Txt_AsmEO.Value = CleanDash(ws.Range("G10").Value)
    Cmb_Team.Value = CStr(ws.Range("I8").Value)
    RefreshNames
    Cmb_Name.Value = CStr(ws.Range("I10").Value)
    Txt_Quote.Value = CStr(ThisWorkbook.Worksheets(SHEET_QUOTE).Range("C3").Value)

    If Len(Txt_Rev.Value) = 0 Then Txt_Rev.Value = "0"
    mLoading = False
End Sub

Private Function CleanDash(ByVal v As Variant) As String
    CleanDash = CStr(v)
    If CleanDash = "-" Then CleanDash = ""
End Function

Private Sub FillCombo(cmb As MSForms.ComboBox, ByVal rangeName As String)
    Dim rng As Range, c As Range
    cmb.Clear
    On Error Resume Next
    Set rng = ThisWorkbook.Names(rangeName).RefersToRange
    On Error GoTo 0
    If rng Is Nothing Then Exit Sub
    For Each c In rng.Cells
        If Len(CStr(c.Value)) > 0 Then cmb.AddItem CStr(c.Value)
    Next c
End Sub

Private Sub RefreshItemNames()
    Dim nm As String
    Select Case Cmb_Item.Value
        Case "샤시": nm = "샤시_품명"
        Case "차체": nm = "차체_품명"
        Case "의장": nm = "의장_품명"
        Case "기타": nm = "기타_품명"
    End Select
    Cmb_ItemName.Clear
    If Len(nm) > 0 Then FillCombo Cmb_ItemName, nm
End Sub

Private Sub RefreshNames()
    If Cmb_Team.Value = "글로벌스트럭쳐팀" Then
        FillCombo Cmb_Name, "샤시기술팀_Name"
    Else
        FillCombo Cmb_Name, "차체기술팀_Name"
    End If
End Sub

Private Sub Cmb_Item_Change()
    If mLoading Then Exit Sub
    RefreshItemNames
    Cmb_ItemName.Value = ""
End Sub

Private Sub Cmb_Team_Change()
    If mLoading Then Exit Sub
    RefreshNames
    Cmb_Name.Value = ""
End Sub

Public Function ApplyToSheet(Optional ByVal saveBook As Boolean = True) As Boolean
    Dim ws As Worksheet, weld As String, asm As String
    On Error GoTo EH
    Set ws = ThisWorkbook.Worksheets(SHEET_MASTER)
    weld = Trim$(Txt_WeldEO.Value): If Len(weld) = 0 Then weld = "-"
    asm = Trim$(Txt_AsmEO.Value): If Len(asm) = 0 Then asm = "-"

    ws.Cells(4, 4).Value = Txt_Customer.Value
    ws.Cells(6, 4).Value = Cmb_Item.Value
    ws.Cells(8, 4).Value = Txt_Project.Value
    ws.Cells(10, 4).Value = Txt_PartNo.Value
    ws.Cells(6, 7).Value = Txt_ItemName.Value
    ws.Cells(4, 7).Value = Cmb_ItemName.Value
    ws.Cells(8, 7).Value = weld
    ws.Cells(10, 7).Value = asm
    ws.Cells(4, 9).Value = Cmb_Step.Value
    ws.Cells(6, 9).Value = Txt_Rev.Value
    ws.Cells(2, 4).Value = Txt_Project.Value & "차종 " & Txt_ItemName.Value & " 개발 마스터"
    ws.Cells(8, 9).Value = Cmb_Team.Value
    ws.Cells(10, 9).Value = Cmb_Name.Value
    ThisWorkbook.Worksheets(SHEET_QUOTE).Cells(3, 3).Value = Txt_Quote.Value

    If saveBook Then
        lblStatus.Caption = "저장 중입니다..."
        DoEvents
        On Error Resume Next
        ThisWorkbook.Save
        On Error GoTo EH
    End If
    ApplyToSheet = True
    Exit Function
EH:
    MsgBox "마스터에 입력하는 중 오류가 발생했습니다." & vbCrLf & Err.Description, vbExclamation, "ITEM 기본정보"
    ApplyToSheet = False
End Function

Private Sub lblSave_Click()
    If Len(Trim$(Txt_Project.Value)) = 0 Or Len(Trim$(Txt_PartNo.Value)) = 0 Then
        MsgBox "차종과 품번은 꼭 입력해주세요.", vbExclamation, "ITEM 기본정보"
        Exit Sub
    End If
    If ApplyToSheet(True) Then Unload Me
End Sub

Private Sub lblCancel_Click()
    Unload Me
End Sub

Private Sub lblSave_MouseMove(ByVal Button As Integer, ByVal Shift As Integer, ByVal X As Single, ByVal Y As Single)
    lblSave.BackColor = RGB(29, 78, 216)
End Sub

Private Sub lblCancel_MouseMove(ByVal Button As Integer, ByVal Shift As Integer, ByVal X As Single, ByVal Y As Single)
    lblCancel.BackColor = RGB(203, 213, 225)
End Sub

Private Sub UserForm_MouseMove(ByVal Button As Integer, ByVal Shift As Integer, ByVal X As Single, ByVal Y As Single)
    lblSave.BackColor = RGB(37, 99, 235)
    lblCancel.BackColor = RGB(226, 232, 240)
End Sub
'''


def add_control(designer, prog_id, name, left, top, width, height, **props):
    ctrl = designer.Controls.Add(prog_id, name, True)
    ctrl.Left, ctrl.Top, ctrl.Width, ctrl.Height = left, top, width, height
    font = props.pop("font", None)
    for key, value in props.items():
        setattr(ctrl, key, value)
    if font:
        ctrl.Font.Name = FONT
        ctrl.Font.Size = font[0]
        ctrl.Font.Bold = font[1]
    return ctrl


def build_form(project):
    comp = project.VBComponents.Add(3)  # vbext_ct_MSForm
    comp.Name = FORM_NAME
    comp.Properties("Caption").Value = "ITEM 기본정보 입력"
    comp.Properties("Width").Value = 462
    comp.Properties("Height").Value = 618
    comp.Properties("BackColor").Value = C_BG
    comp.Properties("StartUpPosition").Value = 1
    d = comp.Designer

    add_control(d, "Forms.Label.1", "lblBanner", 0, 0, 462, 70, BackColor=C_BANNER, BackStyle=1, Caption="")
    add_control(d, "Forms.Label.1", "lblTitle", 20, 14, 400, 26, Caption="ITEM 기본정보 입력",
                ForeColor=C_WHITE, BackStyle=0, font=(15, True))
    add_control(d, "Forms.Label.1", "lblSubtitle", 20, 42, 420, 16,
                Caption="입력한 내용은 마스터 상단 정보와 문서 자동 생성의 기준이 됩니다",
                ForeColor=C_SUB, BackStyle=0, font=(9, False))

    def section(text, top):
        add_control(d, "Forms.Label.1", "lblSec_" + str(top), 20, top, 300, 16, Caption=text,
                    ForeColor=C_BLUE, BackStyle=0, font=(9.5, True))
        add_control(d, "Forms.Label.1", "lblLine_" + str(top), 20, top + 18, 416, 1, Caption="",
                    BackColor=C_LINE, BackStyle=1)

    def field(label, name, left, top, width, kind="text"):
        add_control(d, "Forms.Label.1", "lbl_" + name, left, top, width, 14, Caption=label,
                    ForeColor=C_LABEL, BackStyle=0, font=(8.5, True))
        prog = "Forms.ComboBox.1" if kind == "combo" else "Forms.TextBox.1"
        extra = dict(BackColor=C_WHITE, ForeColor=C_INK, BorderStyle=1, BorderColor=C_LINE,
                     SpecialEffect=0, font=(9.5, False))
        if kind == "combo":
            extra["Style"] = 0
        add_control(d, prog, name, left, top + 15, width, 22, **extra)

    L, R, W = 20, 240, 196

    section("프로젝트 정보", 84)
    field("고객", "Txt_Customer", L, 110, W)
    field("차종", "Txt_Project", R, 110, W)
    field("품번", "Txt_PartNo", L, 158, W)
    field("Rev.", "Txt_Rev", R, 158, W)

    section("ITEM 정보", 210)
    field("아이템", "Cmb_Item", L, 236, W, "combo")
    field("아이템구분", "Cmb_ItemName", R, 236, W, "combo")
    field("아이템명", "Txt_ItemName", L, 284, W)
    field("단계", "Cmb_Step", R, 284, W, "combo")

    section("EO / 담당자", 336)
    field("용접 EO No.", "Txt_WeldEO", L, 362, W)
    field("조립 EO No.", "Txt_AsmEO", R, 362, W)
    field("팀명", "Cmb_Team", L, 410, W, "combo")
    field("담당자", "Cmb_Name", R, 410, W, "combo")
    field("견적명 (1.2 견적투자비 List)", "Txt_Quote", L, 458, 416)

    add_control(d, "Forms.Label.1", "lblSave", 20, 516, 268, 36, Caption="마스터에 입력하고 저장",
                BackColor=C_BLUE, ForeColor=C_WHITE, BackStyle=1, TextAlign=2, BorderStyle=0,
                SpecialEffect=0, font=(11, True), MousePointer=15)
    add_control(d, "Forms.Label.1", "lblCancel", 300, 516, 136, 36, Caption="취소",
                BackColor=C_CANCEL, ForeColor=C_INK, BackStyle=1, TextAlign=2, BorderStyle=0,
                SpecialEffect=0, font=(11, True), MousePointer=15)
    for lbl in ("lblSave", "lblCancel"):
        d.Controls(lbl).TextAlign = 2
    add_control(d, "Forms.Label.1", "lblStatus", 20, 560, 416, 14, Caption="",
                ForeColor=C_LABEL, BackStyle=0, font=(8.5, False))

    code = comp.CodeModule
    if code.CountOfLines > 0:
        code.DeleteLines(1, code.CountOfLines)
    code.AddFromString(FORM_CODE)
    return comp


def build_module(project):
    comp = project.VBComponents.Add(1)  # vbext_ct_StdModule
    comp.Name = MODULE_NAME
    code = comp.CodeModule
    if code.CountOfLines > 0:
        code.DeleteLines(1, code.CountOfLines)
    code.AddFromString(MODULE_CODE)
    return comp


def replace_icon(ws):
    old = ws.Shapes(OLD_ICON)
    left, top = old.Left, old.Top
    print(f"기존 아이콘 {OLD_ICON}: macro={old.OnAction!r} 위치=({left:.1f},{top:.1f}) -> 삭제")
    old.Delete()

    btn = ws.Shapes.AddShape(5, left, top, 62, 34)  # msoShapeRoundedRectangle
    btn.Name = NEW_BUTTON
    btn.Placement = 3  # xlFreeFloating
    try:
        btn.Adjustments[1] = 0.25
    except Exception:
        pass
    btn.Fill.Visible = True
    btn.Fill.TwoColorGradient(1, 1)  # msoGradientHorizontal
    btn.Fill.ForeColor.RGB = rgb(59, 130, 246)
    btn.Fill.BackColor.RGB = rgb(29, 78, 216)
    btn.Line.Visible = False
    btn.Shadow.Visible = True
    btn.Shadow.OffsetX = 1
    btn.Shadow.OffsetY = 2
    btn.Shadow.Blur = 4
    btn.Shadow.Transparency = 0.55
    btn.AlternativeText = "ITEM 기본정보 입력 (고객, 아이템, 차종, 품번, EO, 단계, Rev, 팀, 담당자)"
    tf = btn.TextFrame2
    tf.TextRange.Text = "ITEM 입력"
    tf.TextRange.Font.Name = FONT
    tf.TextRange.Font.Size = 9
    tf.TextRange.Font.Bold = True
    tf.TextRange.Font.Fill.ForeColor.RGB = C_WHITE
    tf.TextRange.ParagraphFormat.Alignment = 2  # msoAlignCenter
    tf.VerticalAnchor = 3  # msoAnchorMiddle
    tf.MarginLeft = tf.MarginRight = 2
    tf.WordWrap = False
    btn.OnAction = "ITEM정보입력"
    return btn


def main(path):
    xl = win32.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    xl.EnableEvents = False
    xl.AutomationSecurity = 3  # 열 때 매크로 실행 안 함
    wb = None
    try:
        t0 = time.time()
        wb = xl.Workbooks.Open(path, 0, False)
        print(f"열기 완료 ({time.time() - t0:.0f}s)")
        project = wb.VBProject
        names = [c.Name for c in project.VBComponents]
        for existing in (FORM_NAME, MODULE_NAME):
            if existing in names:
                project.VBComponents.Remove(project.VBComponents(existing))
        ws = wb.Worksheets(SHEET)

        build_module(project)
        form = build_form(project)
        print("폼/모듈 생성:", FORM_NAME, MODULE_NAME, "| 컨트롤 수:", form.Designer.Controls.Count)

        for sheet in wb.Worksheets:
            if sheet.Name == SHEET:
                continue
            for shp in sheet.Shapes:
                try:
                    if "입력창" in (shp.OnAction or ""):
                        print(f"[참고] 다른 시트에도 '입력창' 연결 도형: {sheet.Name}/{shp.Name}")
                except Exception:
                    pass

        replace_icon(ws)
        wb.Save()
        print(f"저장 완료 ({time.time() - t0:.0f}s)")
        wb.Close(False)
        wb = None
        return 0
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        if wb is not None:
            try:
                wb.Close(False)
            except Exception:
                pass
        xl.Quit()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1]))
