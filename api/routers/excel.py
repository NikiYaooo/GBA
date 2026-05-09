import io
import base64
import tempfile
from fastapi import APIRouter, Body, Request
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

router = APIRouter(prefix="/api/excel", tags=["excel"])


@router.post("/parse")
async def parse_excel(request: Request):
    try:
        raw_bytes = await request.body()
        if not raw_bytes or len(raw_bytes) < 20:
            return {"success": False, "message": "上传内容为空"}

        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=False)
        wb_data = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
        sheets = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            ws_data = wb_data[sheet_name]
            rows = []
            for ri, row in enumerate(ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column), 1):
                row_data = []
                for ci, cell in enumerate(row, 1):
                    formula = ""
                    computed_val = cell.value
                    if isinstance(cell.value, str) and cell.value.startswith("="):
                        formula = cell.value
                        try:
                            computed_val = ws_data.cell(row=ri, column=ci).value
                        except Exception:
                            pass
                    row_data.append({
                        "v": str(computed_val) if computed_val is not None else "",
                        "f": formula
                    })
                rows.append(row_data)
            sheets.append({
                "name": sheet_name,
                "rows": rows,
                "max_row": len(rows),
                "max_col": max(len(r) for r in rows) if rows else 0
            })
        wb.close()
        wb_data.close()
        return {"success": True, "data": {"sheets": sheets}}
    except Exception as e:
        return {"success": False, "message": f"Excel解析失败: {str(e)}"}


@router.post("/save")
async def save_excel(payload: dict = Body(...)):
    try:
        import openpyxl
        sheets_data = payload.get("sheets", [])
        if not sheets_data:
            return {"success": False, "message": "没有数据"}

        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        for sd in sheets_data:
            ws = wb.create_sheet(title=sd.get("name", "Sheet1"))
            rows = sd.get("rows", [])
            for ri, row in enumerate(rows, 1):
                for ci, cell_data in enumerate(row, 1):
                    cell = ws.cell(row=ri, column=ci)
                    formula = cell_data.get("f", "")
                    value = cell_data.get("v", "")
                    if formula:
                        cell.value = formula
                    else:
                        cell.value = value
                    color = cell_data.get("color", "")
                    if color and color != '#ffffff' and color != '#000000':
                        cell.fill = PatternFill(
                            start_color=color.lstrip('#'),
                            end_color=color.lstrip('#'),
                            fill_type='solid'
                        )
                    cell.border = thin_border
                    cell.alignment = Alignment(horizontal='center', vertical='center')

        tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        wb.save(tmp.name)
        wb.close()
        with open(tmp.name, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        import os
        os.unlink(tmp.name)
        return {"success": True, "data_uri": f"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}"}
    except Exception as e:
        return {"success": False, "message": f"Excel保存失败: {str(e)}"}
