import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { apiUrl } from '@/utils/api'
import type { DocRecord, ExcelState, ApiResponse } from '@/types'

export interface CellCoord {
  ri: number
  ci: number
}

export interface ContextMenuState {
  show: boolean
  x: number
  y: number
  ri: number
  ci: number
}

export function useExcel() {
  const excelData = ref<ExcelState | null>(null)
  const excelFilePath = ref('')
  const excelFillColor = ref('#ffffff')
  const selectedCell = ref<CellCoord | null>(null)
  const copiedCell = ref<{ v: string; f: string } | null>(null)
  const contextMenu = ref<ContextMenuState>({ show: false, x: 0, y: 0, ri: -1, ci: -1 })

  const loadExcelData = async (doc: DocRecord) => {
    try {
      const r = await axios.get<ApiResponse<DocRecord>>(apiUrl(`/api/documents/${doc.id}`))
      if (!r.data.success || !r.data.data?.path) return
      excelFilePath.value = r.data.data.path
      const fileRes = await axios.get(apiUrl(`/api/documents/file/${doc.id}`), { responseType: 'arraybuffer' })
      if (!fileRes.data) return
      const parseRes = await axios.post(apiUrl('/api/excel/parse'), fileRes.data, {
        headers: { 'Content-Type': 'application/octet-stream', 'X-Filename': encodeURIComponent(doc.name) },
        timeout: 10000
      })
      if (parseRes.data.success) {
        const sheets = parseRes.data.data.sheets || []
        excelData.value = { sheets, activeSheet: 0 }
      }
    } catch { /* */ }
  }

  const getSheet = () => {
    if (!excelData.value) return null
    return excelData.value.sheets[excelData.value.activeSheet]
  }

  const selectCell = (ri: number, ci: number) => {
    selectedCell.value = { ri, ci }
    closeContextMenu()
  }

  const updateCell = (sheetIdx: number, ri: number, ci: number, value: string) => {
    if (!excelData.value || !excelData.value.sheets[sheetIdx]) return
    const sheet = excelData.value.sheets[sheetIdx]
    if (!sheet.rows[ri]) sheet.rows[ri] = []
    if (!sheet.rows[ri][ci]) sheet.rows[ri][ci] = { v: '', f: '' }
    sheet.rows[ri][ci].v = value
    sheet.rows[ri][ci].f = ''
  }

  const setCellColor = (ri: number, ci: number, color: string) => {
    const sheet = getSheet()
    if (!sheet) return
    if (!sheet.rows[ri]) sheet.rows[ri] = []
    if (!sheet.rows[ri][ci]) sheet.rows[ri][ci] = { v: '', f: '' }
    sheet.rows[ri][ci].color = color
  }

  const clearCell = () => {
    const s = selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet) return
    if (sheet.rows[s.ri] && sheet.rows[s.ri][s.ci]) {
      sheet.rows[s.ri][s.ci] = { v: '', f: '' }
    }
  }

  const copyCell = () => {
    const s = selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet || !sheet.rows[s.ri] || !sheet.rows[s.ri][s.ci]) return
    copiedCell.value = { ...sheet.rows[s.ri][s.ci] }
    ElMessage.success('已复制')
    closeContextMenu()
  }

  const pasteCell = () => {
    const s = selectedCell.value
    if (!s || !copiedCell.value) return
    const sheet = getSheet()
    if (!sheet) return
    if (!sheet.rows[s.ri]) sheet.rows[s.ri] = []
    sheet.rows[s.ri][s.ci] = { ...copiedCell.value }
    closeContextMenu()
  }

  const insertRowAbove = () => {
    const s = selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet) return
    const newRow = Array.from({ length: sheet.max_col || 1 }, () => ({ v: '', f: '' }))
    sheet.rows.splice(s.ri, 0, newRow)
    sheet.max_row = sheet.rows.length
    closeContextMenu()
  }

  const insertRowBelow = () => {
    const s = selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet) return
    const newRow = Array.from({ length: sheet.max_col || 1 }, () => ({ v: '', f: '' }))
    sheet.rows.splice(s.ri + 1, 0, newRow)
    sheet.max_row = sheet.rows.length
    closeContextMenu()
  }

  const insertColLeft = () => {
    const s = selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet) return
    sheet.max_col = (sheet.max_col || 1) + 1
    for (const row of sheet.rows) {
      row.splice(s.ci, 0, { v: '', f: '' })
    }
    closeContextMenu()
  }

  const insertColRight = () => {
    const s = selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet) return
    sheet.max_col = (sheet.max_col || 1) + 1
    for (const row of sheet.rows) {
      row.splice(s.ci + 1, 0, { v: '', f: '' })
    }
    closeContextMenu()
  }

  const deleteRow = () => {
    const s = selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet || sheet.rows.length <= 1) return
    sheet.rows.splice(s.ri, 1)
    sheet.max_row = sheet.rows.length
    selectedCell.value = s.ri >= sheet.rows.length ? { ri: sheet.rows.length - 1, ci: s.ci } : { ri: s.ri, ci: s.ci }
    closeContextMenu()
  }

  const deleteCol = () => {
    const s = selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet || (sheet.max_col || 1) <= 1) return
    for (const row of sheet.rows) {
      if (s.ci < row.length) row.splice(s.ci, 1)
    }
    sheet.max_col = Math.max(1, ...sheet.rows.map(r => r.length))
    selectedCell.value = { ri: s.ri, ci: Math.min(s.ci, (sheet.max_col || 1) - 1) }
    closeContextMenu()
  }

  const moveSelection = (dRi: number, dCi: number) => {
    const sheet = getSheet()
    if (!sheet) return
    const s = selectedCell.value
    if (!s) return
    let newRi = s.ri + dRi
    let newCi = s.ci + dCi
    newRi = Math.max(0, Math.min(newRi, sheet.rows.length - 1))
    newCi = Math.max(0, Math.min(newCi, (sheet.max_col || 1) - 1))
    selectedCell.value = { ri: newRi, ci: newCi }
  }

  const handleCellKeydown = (e: KeyboardEvent) => {
    const s = selectedCell.value
    if (!s) return
    if (e.key === 'Tab') {
      e.preventDefault()
      if (e.shiftKey) moveSelection(0, -1)
      else moveSelection(0, 1)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (e.shiftKey) moveSelection(-1, 0)
      else moveSelection(1, 0)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault(); moveSelection(-1, 0)
    } else if (e.key === 'ArrowDown') {
      e.preventDefault(); moveSelection(1, 0)
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault(); moveSelection(0, -1)
    } else if (e.key === 'ArrowRight') {
      e.preventDefault(); moveSelection(0, 1)
    } else if (e.key === 'Delete' || e.key === 'Backspace') {
      clearCell()
    } else if (e.ctrlKey && e.key === 'c') {
      copyCell()
    } else if (e.ctrlKey && e.key === 'v') {
      pasteCell()
    }
  }

  const showContextMenu = (e: MouseEvent, ri: number, ci: number) => {
    e.preventDefault()
    e.stopPropagation()
    selectedCell.value = { ri, ci }
    contextMenu.value = { show: true, x: e.clientX, y: e.clientY, ri, ci }
  }

  const closeContextMenu = () => {
    contextMenu.value.show = false
  }

  const addRow = () => {
    if (!excelData.value) return
    const sheet = excelData.value.sheets[excelData.value.activeSheet]
    const newRow = Array.from({ length: sheet.max_col || 1 }, () => ({ v: '', f: '' }))
    sheet.rows.push(newRow)
    sheet.max_row = sheet.rows.length
  }

  const addCol = () => {
    if (!excelData.value) return
    const sheet = excelData.value.sheets[excelData.value.activeSheet]
    sheet.max_col = (sheet.max_col || 1) + 1
    for (const row of sheet.rows) row.push({ v: '', f: '' })
  }

  const saveToFile = async (doc: DocRecord): Promise<string> => {
    if (!excelData.value) throw new Error('Excel 数据未加载')
    const saveRes = await axios.post(apiUrl('/api/excel/save'), { sheets: excelData.value.sheets })
    if (!saveRes.data.success) throw new Error(saveRes.data.message || 'Excel 保存接口返回失败')
    if (!saveRes.data.data_uri) throw new Error('保存后未获取到文件数据')
    return saveRes.data.data_uri
  }

  const initEmpty = () => {
    const emptyRow: { v: string; f: string }[] = []
    for (let i = 0; i < 10; i++) emptyRow.push({ v: '', f: '' })
    excelData.value = {
      sheets: [{ name: 'Sheet1', rows: [emptyRow], max_row: 1, max_col: 10 }],
      activeSheet: 0
    }
  }

  const reset = () => {
    excelData.value = null
    excelFilePath.value = ''
    selectedCell.value = null
    contextMenu.value = { show: false, x: 0, y: 0, ri: -1, ci: -1 }
  }

  return {
    excelData, excelFilePath, excelFillColor, selectedCell, copiedCell, contextMenu,
    loadExcelData, updateCell, setCellColor,
    addRow, addCol, clearCell, copyCell, pasteCell,
    insertRowAbove, insertRowBelow, insertColLeft, insertColRight,
    deleteRow, deleteCol, moveSelection, selectCell,
    handleCellKeydown, showContextMenu, closeContextMenu,
    saveToFile, initEmpty, reset,
  }
}
