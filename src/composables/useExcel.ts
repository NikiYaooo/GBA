import { ref, computed, nextTick } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { apiUrl } from '@/utils/api'
import type { CellData, DocRecord, ExcelState, ApiResponse } from '@/types'

export interface CellCoord {
  ri: number
  ci: number
}

export interface CellRange {
  minRi: number; maxRi: number
  minCi: number; maxCi: number
}

export interface ContextMenuState {
  show: boolean
  x: number
  y: number
  ri: number
  ci: number
}

interface PerSheetState {
  selectedCell: CellCoord | null
  selectionAnchor: CellCoord | null
  colWidths: Record<number, number>
  editCell: CellCoord | null
}

// ========== 公式引擎 ==========

/** 解析列字母 → 0-based index (A=0, B=1, ..., Z=25, AA=26) */
function colIndex(col: string): number {
  let idx = 0
  for (let i = 0; i < col.length; i++) idx = idx * 26 + (col.charCodeAt(i) - 64)
  return idx - 1
}

/** 解析单元格引用 "A1" → {ri, ci} */
function parseCellRef(ref: string): CellCoord {
  const m = ref.match(/^([A-Z]+)(\d+)$/)
  if (!m) throw new Error(`无效单元格引用: ${ref}`)
  return { ci: colIndex(m[1]), ri: parseInt(m[2]) - 1 }
}

/** 展开范围 "A1:B3" 或逗号分隔列表 */
function expandArgs(args: string, getVal: (ri: number, ci: number) => number): number[] {
  const parts = args.split(',').map(s => s.trim()).filter(Boolean)
  const nums: number[] = []
  for (const p of parts) {
    if (p.includes(':')) {
      const [a, b] = p.split(':')
      const s = parseCellRef(a), e = parseCellRef(b)
      for (let ri = Math.min(s.ri, e.ri); ri <= Math.max(s.ri, e.ri); ri++)
        for (let ci = Math.min(s.ci, e.ci); ci <= Math.max(s.ci, e.ci); ci++)
          nums.push(getVal(ri, ci))
    } else if (/^[A-Z]+\d+$/.test(p)) {
      const { ri, ci } = parseCellRef(p)
      nums.push(getVal(ri, ci))
    } else {
      nums.push(parseFloat(p) || 0)
    }
  }
  return nums
}

/** 计算公式，返回计算结果字符串 */
function calcFormula(formula: string, getVal: (ri: number, ci: number) => number): string | null {
  try {
    let expr = formula.replace(/^=\s*/, '')
    // 先展开函数调用（从内到外）
    let prev = ''
    while (prev !== expr) {
      prev = expr
      expr = expr.replace(/(SUM|AVERAGE|MIN|MAX|COUNT)\(([^()]*)\)/gi, (_, fn: string, args: string) => {
        const vals = expandArgs(args, getVal)
        switch (fn.toUpperCase()) {
          case 'SUM': return String(vals.reduce((a, b) => a + b, 0))
          case 'AVERAGE': return vals.length ? String(vals.reduce((a, b) => a + b, 0) / vals.length) : '0'
          case 'MIN': return vals.length ? String(Math.min(...vals)) : '0'
          case 'MAX': return vals.length ? String(Math.max(...vals)) : '0'
          case 'COUNT': return String(vals.length)
          default: return '0'
        }
      })
    }
    // 替换单元格引用为数值
    expr = expr.replace(/([A-Z]+)(\d+)/g, (_, col: string, row: string) => {
      const { ri, ci } = parseCellRef(col + row)
      return String(getVal(ri, ci))
    })
    // 安全算术求值
    const sanitized = expr.replace(/[^0-9+\-*/.()eE\s]/g, '')
    if (!sanitized) return null
    const result = new Function(`return (${sanitized})`)()
    const num = typeof result === 'number' && !isNaN(result) ? result : 0
    // 小数处理：保留 2 位
    return Number.isInteger(num) ? String(num) : num.toFixed(2)
  } catch {
    return null
  }
}

// ========== Composable ==========

export function useExcel() {
  const excelData = ref<ExcelState | null>(null)
  const excelFilePath = ref('')
  const excelFillColor = ref('#ffff00')  // 默认黄色
  const excelTextColor = ref('#000000')   // 默认黑色
  const selectedCell = ref<CellCoord | null>(null)
  const selectionAnchor = ref<CellCoord | null>(null)
  const editCell = ref<CellCoord | null>(null)
  const copiedData = ref<CellData[][] | null>(null)
  const contextMenu = ref<ContextMenuState>({ show: false, x: 0, y: 0, ri: -1, ci: -1 })
  const isDragging = ref(false)
  /** 拖拽过程中是否真的移动过（区分点击和拖拽） */
  const dragDidMove = ref(false)
  const colWidths = ref<Record<number, number>>({})
  const editingFormula = ref('')
  const undoStack = ref<string[]>([])
  const redoStack = ref<string[]>([])
  const maxUndo = 15
  const sheetStates = ref<Record<number, PerSheetState>>({})
  const excelLoading = ref(false)

  // ========== 选区范围 ==========

  const selectedRange = computed<CellRange | null>(() => {
    if (!selectionAnchor.value || !selectedCell.value) return null
    return {
      minRi: Math.min(selectionAnchor.value.ri, selectedCell.value.ri),
      maxRi: Math.max(selectionAnchor.value.ri, selectedCell.value.ri),
      minCi: Math.min(selectionAnchor.value.ci, selectedCell.value.ci),
      maxCi: Math.max(selectionAnchor.value.ci, selectedCell.value.ci),
    }
  })

  const isInRange = (ri: number, ci: number) => {
    const r = selectedRange.value
    if (!r) return false
    return ri >= r.minRi && ri <= r.maxRi && ci >= r.minCi && ci <= r.maxCi
  }

  const isActiveCell = (ri: number, ci: number) =>
    selectedCell.value?.ri === ri && selectedCell.value?.ci === ci

  /** 遍历当前范围中的所有单元格坐标 */
  const eachInRange = (fn: (ri: number, ci: number) => void) => {
    const r = selectedRange.value
    if (!r) {
      const s = editCell.value || selectedCell.value
      if (s) fn(s.ri, s.ci)
      return
    }
    for (let ri = r.minRi; ri <= r.maxRi; ri++)
      for (let ci = r.minCi; ci <= r.maxCi; ci++)
        fn(ri, ci)
  }

  // ========== 公式重算 ==========

  const recalculateFormulas = () => {
    const sheet = getSheet()
    if (!sheet) return
    const getVal = (ri: number, ci: number): number => {
      if (!sheet.rows[ri] || !sheet.rows[ri][ci]) return 0
      const n = parseFloat(sheet.rows[ri][ci].v)
      return isNaN(n) ? 0 : n
    }
    // 先收集所有公式单元格坐标
    const formulaCells: { ri: number; ci: number }[] = []
    for (let ri = 0; ri < sheet.rows.length; ri++) {
      const row = sheet.rows[ri]
      if (!row) continue
      for (let ci = 0; ci < row.length; ci++) {
        if (row[ci]?.f?.startsWith('=')) formulaCells.push({ ri, ci })
      }
    }
    if (formulaCells.length === 0) return
    // 公式少用 5 轮收敛，公式多时 3 轮就够了（级联深度有限）
    const maxIter = formulaCells.length < 50 ? 5 : 3
    for (let iter = 0; iter < maxIter; iter++) {
      let changed = false
      for (const { ri, ci } of formulaCells) {
        const cell = sheet.rows[ri][ci]
        const oldV = cell.v
        const newV = calcFormula(cell.f, getVal)
        if (newV !== null && newV !== oldV) {
          cell.v = newV
          changed = true
        }
      }
      if (!changed) break
    }
  }

  // ========== 撤销 ==========

  const pushUndo = () => {
    if (!excelData.value) return
    const snap = JSON.stringify(excelData.value)
    if (undoStack.value.length > 0 && undoStack.value[undoStack.value.length - 1] === snap) return
    undoStack.value.push(snap)
    if (undoStack.value.length > maxUndo) undoStack.value.shift()
    redoStack.value = []
  }

  const undo = () => {
    if (undoStack.value.length === 0) return
    redoStack.value.push(JSON.stringify(excelData.value))
    excelData.value = JSON.parse(undoStack.value.pop()!)
    selectedCell.value = null
    selectionAnchor.value = null
    editCell.value = null
  }

  const redo = () => {
    if (redoStack.value.length === 0) return
    pushUndo()
    excelData.value = JSON.parse(redoStack.value.pop()!)
    selectedCell.value = null
    selectionAnchor.value = null
    editCell.value = null
  }

  // ========== 编辑模式 ==========

  const isEditing = (ri: number, ci: number) =>
    editCell.value?.ri === ri && editCell.value?.ci === ci

  const startEdit = async (ri: number, ci: number) => {
    endEdit(true)
    editCell.value = { ri, ci }
    selectedCell.value = { ri, ci }
    selectionAnchor.value = { ri, ci }
    closeContextMenu()
    const sheet = getSheet()
    if (sheet && sheet.rows[ri] && sheet.rows[ri][ci]) {
      editingFormula.value = sheet.rows[ri][ci].f || sheet.rows[ri][ci].v
    } else {
      editingFormula.value = ''
    }
    await nextTick()
    // 聚焦 contenteditable
    const el = document.querySelector<HTMLElement>(`[data-cell-edit="${ri}-${ci}"]`)
    el?.focus()
  }

  const endEdit = (commit: boolean) => {
    if (!editCell.value) return
    if (commit) commitFormula()
    editCell.value = null
  }

  // ========== Sheet ==========

  const saveSheetState = () => {
    if (!excelData.value) return
    const idx = excelData.value.activeSheet
    sheetStates.value[idx] = {
      selectedCell: selectedCell.value ? { ...selectedCell.value } : null,
      selectionAnchor: selectionAnchor.value ? { ...selectionAnchor.value } : null,
      colWidths: { ...colWidths.value },
      editCell: null,
    }
  }

  const restoreSheetState = (idx: number) => {
    const st = sheetStates.value[idx]
    if (st) {
      selectedCell.value = st.selectedCell
      selectionAnchor.value = st.selectionAnchor
      colWidths.value = st.colWidths
    } else {
      selectedCell.value = null
      selectionAnchor.value = null
    }
    editCell.value = null
  }

  const switchSheet = (idx: number) => {
    if (!excelData.value) return
    endEdit(true)
    saveSheetState()
    excelData.value.activeSheet = idx
    restoreSheetState(idx)
  }

  // ========== 数据加载 ==========

  const loadExcelData = async (doc: DocRecord) => {
    excelLoading.value = true
    try {
      excelFilePath.value = doc.path || ''
      const fileRes = await axios.get(apiUrl(`/api/documents/file/${doc.id}`), { responseType: 'arraybuffer' })
      if (!fileRes.data) { excelLoading.value = false; return }
      const parseRes = await axios.post(apiUrl('/api/excel/parse'), fileRes.data, {
        headers: { 'Content-Type': 'application/octet-stream', 'X-Filename': encodeURIComponent(doc.name) },
        timeout: 10000,
      })
      if (parseRes.data.success) {
        excelData.value = { sheets: parseRes.data.data.sheets || [], activeSheet: 0 }
        sheetStates.value = {}
        selectedCell.value = null
        selectionAnchor.value = null
        editCell.value = null
        colWidths.value = {}
        undoStack.value = []
      } else {
        ElMessage.error(parseRes.data.message || 'Excel 解析失败')
      }
      excelLoading.value = false
    } catch (e: any) {
      excelLoading.value = false
      ElMessage.error(`Excel 加载失败: ${e?.message || '未知错误'}`)
    }
  }

  const getSheet = () => {
    if (!excelData.value) return null
    return excelData.value.sheets[excelData.value.activeSheet]
  }

  // ========== 选中 + 公式栏 ==========

  const selectCell = (ri: number, ci: number, shiftKey = false) => {
    if (editCell.value) return  // 编辑中不响应选区变化
    if (dragDidMove.value) { dragDidMove.value = false; return }  // 拖拽后不重置选区
    if (shiftKey && selectionAnchor.value) {
      // Shift+Click 扩展选区
      selectedCell.value = { ri, ci }
    } else {
      selectionAnchor.value = { ri, ci }
      selectedCell.value = { ri, ci }
    }
    closeContextMenu()
    const sheet = getSheet()
    if (sheet && sheet.rows[ri] && sheet.rows[ri][ci]) {
      editingFormula.value = sheet.rows[ri][ci].f || sheet.rows[ri][ci].v
    } else {
      editingFormula.value = ''
    }
  }

  // ========== 单元格写入 ==========

  function emptyCell(): CellData {
    return { v: '', f: '' }
  }

  const writeCell = (ri: number, ci: number, raw: string) => {
    const sheet = getSheet()
    if (!sheet) return
    if (!sheet.rows[ri]) sheet.rows[ri] = []
    if (!sheet.rows[ri][ci]) sheet.rows[ri][ci] = { v: '', f: '' }
    const trimmed = raw.trim()
    const cell = sheet.rows[ri][ci]
    if (trimmed.startsWith('=')) {
      cell.f = trimmed
      cell.v = calcFormula(trimmed, (r, c) => {
        if (!sheet.rows[r] || !sheet.rows[r][c]) return 0
        return parseFloat(sheet.rows[r][c].v) || 0
      }) || trimmed
    } else {
      cell.v = trimmed
      cell.f = ''
    }
  }

  const commitFormula = () => {
    const s = editCell.value || selectedCell.value
    if (!s) return
    if (!editingFormula.value && !editCell.value) return
    const sheet = getSheet()
    if (!sheet) return
    pushUndo()
    writeCell(s.ri, s.ci, editingFormula.value)
    recalculateFormulas()
  }

  const cancelEdit = () => {
    if (!editCell.value) return
    const sheet = getSheet()
    if (sheet && sheet.rows[editCell.value.ri]?.[editCell.value.ci]) {
      const cell = sheet.rows[editCell.value.ri][editCell.value.ci]
      editingFormula.value = cell.f || cell.v
    }
    editCell.value = null
  }

  // ========== 单元格格式操作 ==========

  const toggleBold = () => {
    pushUndo()
    eachInRange((ri, ci) => {
      const sheet = getSheet()
      if (!sheet) return
      if (!sheet.rows[ri]) sheet.rows[ri] = []
      if (!sheet.rows[ri][ci]) sheet.rows[ri][ci] = emptyCell()
      sheet.rows[ri][ci].bold = !sheet.rows[ri][ci].bold
    })
  }

  const toggleItalic = () => {
    pushUndo()
    eachInRange((ri, ci) => {
      const sheet = getSheet()
      if (!sheet) return
      if (!sheet.rows[ri]) sheet.rows[ri] = []
      if (!sheet.rows[ri][ci]) sheet.rows[ri][ci] = emptyCell()
      sheet.rows[ri][ci].italic = !sheet.rows[ri][ci].italic
    })
  }

  const toggleUnderline = () => {
    pushUndo()
    eachInRange((ri, ci) => {
      const sheet = getSheet()
      if (!sheet) return
      if (!sheet.rows[ri]) sheet.rows[ri] = []
      if (!sheet.rows[ri][ci]) sheet.rows[ri][ci] = emptyCell()
      sheet.rows[ri][ci].underline = !sheet.rows[ri][ci].underline
    })
  }

  const toggleStrikethrough = () => {
    pushUndo()
    eachInRange((ri, ci) => {
      const sheet = getSheet()
      if (!sheet) return
      if (!sheet.rows[ri]) sheet.rows[ri] = []
      if (!sheet.rows[ri][ci]) sheet.rows[ri][ci] = emptyCell()
      sheet.rows[ri][ci].strikethrough = !sheet.rows[ri][ci].strikethrough
    })
  }

  const setCellFontSize = (size: number) => {
    pushUndo()
    eachInRange((ri, ci) => {
      const sheet = getSheet()
      if (!sheet) return
      if (!sheet.rows[ri]) sheet.rows[ri] = []
      if (!sheet.rows[ri][ci]) sheet.rows[ri][ci] = emptyCell()
      sheet.rows[ri][ci].fontSize = size
    })
  }

  const setCellFontFamily = (family: string) => {
    pushUndo()
    eachInRange((ri, ci) => {
      const sheet = getSheet()
      if (!sheet) return
      if (!sheet.rows[ri]) sheet.rows[ri] = []
      if (!sheet.rows[ri][ci]) sheet.rows[ri][ci] = emptyCell()
      sheet.rows[ri][ci].fontFamily = family
    })
  }

  const setCellTextColor = (color: string) => {
    pushUndo()
    eachInRange((ri, ci) => {
      const sheet = getSheet()
      if (!sheet) return
      if (!sheet.rows[ri]) sheet.rows[ri] = []
      if (!sheet.rows[ri][ci]) sheet.rows[ri][ci] = emptyCell()
      sheet.rows[ri][ci].textColor = color
    })
  }

  const setCellTextAlign = (align: 'left' | 'center' | 'right') => {
    pushUndo()
    eachInRange((ri, ci) => {
      const sheet = getSheet()
      if (!sheet) return
      if (!sheet.rows[ri]) sheet.rows[ri] = []
      if (!sheet.rows[ri][ci]) sheet.rows[ri][ci] = emptyCell()
      sheet.rows[ri][ci].textAlign = align
    })
  }

  const clearCellFormat = () => {
    pushUndo()
    eachInRange((ri, ci) => {
      const sheet = getSheet()
      if (!sheet) return
      if (!sheet.rows[ri]?.[ci]) return
      const cell = sheet.rows[ri][ci]
      cell.bold = undefined
      cell.italic = undefined
      cell.underline = undefined
      cell.strikethrough = undefined
      cell.fontSize = undefined
      cell.fontFamily = undefined
      cell.textColor = undefined
      cell.textAlign = undefined
      cell.color = undefined
    })
  }

  const updateCell = (sheetIdx: number, ri: number, ci: number, value: string) => {
    if (!excelData.value || !excelData.value.sheets[sheetIdx]) return
    pushUndo()
    writeCell(ri, ci, value)
    recalculateFormulas()
  }

  /** 键盘直接输入：在当前选中/编辑格写入字符 */
  const typeChar = (ch: string) => {
    const s = editCell.value || selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet) return
    // 进入编辑模式（如果还没在编辑）
    if (!editCell.value) {
      startEdit(s.ri, s.ci)
    }
    // contenteditable 已经 focus，浏览器会处理字符输入
  }

  // ========== 颜色填充 ==========

  const applyColorToSelection = () => {
    const sheet = getSheet()
    if (!sheet) return
    pushUndo()
    eachInRange((ri, ci) => {
      if (!sheet.rows[ri]) sheet.rows[ri] = []
      if (!sheet.rows[ri][ci]) sheet.rows[ri][ci] = emptyCell()
      sheet.rows[ri][ci].color = excelFillColor.value
    })
  }

  const clearCell = () => {
    const sheet = getSheet()
    if (!sheet) return
    pushUndo()
    eachInRange((ri, ci) => {
      if (sheet.rows[ri] && sheet.rows[ri][ci]) {
        const cell = sheet.rows[ri][ci]
        cell.v = ''
        cell.f = ''
      }
    })
  }

  // ========== 复制 / 粘贴 ==========

  const copySelection = () => {
    const sheet = getSheet()
    if (!sheet) return
    const r = selectedRange.value
    if (!r) {
      const s = editCell.value || selectedCell.value
      if (!s || !sheet.rows[s.ri] || !sheet.rows[s.ri][s.ci]) return
      copiedData.value = [[{ ...sheet.rows[s.ri][s.ci] }]]
      ElMessage.success('已复制')
      closeContextMenu()
      return
    }
    const data: CellData[][] = []
    for (let ri = r.minRi; ri <= r.maxRi; ri++) {
      const row: CellData[] = []
      for (let ci = r.minCi; ci <= r.maxCi; ci++) {
        row.push(sheet.rows[ri]?.[ci] ? { ...sheet.rows[ri][ci] } : emptyCell())
      }
      data.push(row)
    }
    copiedData.value = data
    // 同时写入系统剪贴板（Tab 分隔）
    const text = data.map(r => r.map(c => c.f || c.v).join('\t')).join('\n')
    navigator.clipboard.writeText(text).catch(() => {})
    ElMessage.success(`已复制 ${data.length} 行 × ${data[0]?.length || 0} 列`)
    closeContextMenu()
  }

  const pasteToSelection = () => {
    const s = editCell.value || selectedCell.value
    if (!s) return
    // 有内部复制数据时直接粘贴
    if (copiedData.value) {
      pasteCellData(s, copiedData.value)
      return
    }
    // 无内部数据时从系统剪贴板读取
    pasteFromSystemClipboard(s)
  }

  const pasteCellData = (s: CellCoord, data: CellData[][]) => {
    const sheet = getSheet()
    if (!sheet) return
    pushUndo()
    for (let ri = 0; ri < data.length; ri++) {
      const targetRi = s.ri + ri
      if (!sheet.rows[targetRi]) sheet.rows[targetRi] = []
      for (let ci = 0; ci < data[ri].length; ci++) {
        const targetCi = s.ci + ci
        while (sheet.rows[targetRi].length <= targetCi) {
          sheet.rows[targetRi].push(emptyCell())
        }
        const src = data[ri][ci]
        if (src.f && src.f.startsWith('=')) {
          const adjusted = shiftFormulaRefs(src.f, ri, ci)
          sheet.rows[targetRi][targetCi] = { ...src, f: adjusted, v: '' }
        } else {
          sheet.rows[targetRi][targetCi] = { ...src }
        }
      }
    }
    sheet.max_row = Math.max(sheet.max_row, sheet.rows.length)
    sheet.max_col = Math.max(sheet.max_col || 0, ...sheet.rows.map(r => r.length))
    recalculateFormulas()
    closeContextMenu()
  }

  const pasteFromSystemClipboard = async (s: CellCoord) => {
    try {
      const text = await navigator.clipboard.readText()
      if (!text) return
      const rows = text.split('\n').filter(r => r.length > 0)
      const data: CellData[][] = rows.map(r =>
        r.split('\t').map(c => {
          const trimmed = c.trim()
          return trimmed.startsWith('=')
            ? { v: '', f: trimmed }
            : { v: trimmed, f: '' }
        })
      )
      if (data.length === 0) return
      pasteCellData(s, data)
    } catch {
      // 剪贴板读取失败（无权限等），静默处理
    }
  }

  /** 粘贴时偏移公式中的引用（相对位置） */
  function shiftFormulaRefs(formula: string, dRi: number, dCi: number): string {
    return formula.replace(/([A-Z]+)(\d+)/g, (_m, col, row) => {
      const ci = colIndex(col) + dCi
      const ri = parseInt(row) + dRi
      // 超出范围则保持绝对引用
      if (ci < 0 || ri < 0) return _m
      return toColLetter(ci) + (ri + 1)
    })
  }

  function toColLetter(ci: number): string {
    let s = ''
    let n = ci + 1
    while (n > 0) {
      n--
      s = String.fromCharCode(65 + (n % 26)) + s
      n = Math.floor(n / 26)
    }
    return s
  }

  // ========== 行/列 操作 ==========

  const insertRowAbove = () => {
    const s = editCell.value || selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet) return
    pushUndo()
    const newRow = Array.from({ length: sheet.max_col || 1 }, () => emptyCell())
    sheet.rows.splice(s.ri, 0, newRow)
    sheet.max_row = sheet.rows.length
    closeContextMenu()
  }

  const insertRowBelow = () => {
    const s = editCell.value || selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet) return
    pushUndo()
    const newRow = Array.from({ length: sheet.max_col || 1 }, () => emptyCell())
    sheet.rows.splice(s.ri + 1, 0, newRow)
    sheet.max_row = sheet.rows.length
    closeContextMenu()
  }

  const insertColLeft = () => {
    const s = editCell.value || selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet) return
    pushUndo()
    sheet.max_col = (sheet.max_col || 1) + 1
    for (const row of sheet.rows) row.splice(s.ci, 0, emptyCell())
    closeContextMenu()
  }

  const insertColRight = () => {
    const s = editCell.value || selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet) return
    pushUndo()
    sheet.max_col = (sheet.max_col || 1) + 1
    for (const row of sheet.rows) row.splice(s.ci + 1, 0, emptyCell())
    closeContextMenu()
  }

  const deleteRow = () => {
    const s = editCell.value || selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet || sheet.rows.length <= 1) return
    pushUndo()
    sheet.rows.splice(s.ri, 1)
    sheet.max_row = sheet.rows.length
    const newRi = Math.min(s.ri, Math.max(0, sheet.rows.length - 1))
    selectedCell.value = { ri: newRi, ci: s.ci }
    selectionAnchor.value = { ri: newRi, ci: s.ci }
    editCell.value = null
    recalculateFormulas()
    closeContextMenu()
  }

  const deleteCol = () => {
    const s = editCell.value || selectedCell.value
    if (!s) return
    const sheet = getSheet()
    if (!sheet || (sheet.max_col || 0) <= 1) return
    pushUndo()
    for (const row of sheet.rows) {
      if (s.ci < row.length) row.splice(s.ci, 1)
    }
    const maxLen = sheet.rows.length > 0 ? Math.max(...sheet.rows.map(r => r.length)) : 1
    sheet.max_col = Math.max(1, maxLen)
    const newCi = Math.min(s.ci, Math.max(0, (sheet.max_col || 1) - 1))
    selectedCell.value = { ri: s.ri, ci: newCi }
    selectionAnchor.value = { ri: s.ri, ci: newCi }
    editCell.value = null
    recalculateFormulas()
    closeContextMenu()
  }

  // ========== 导航 ==========

  const moveSelection = (dRi: number, dCi: number, shiftKey = false) => {
    const sheet = getSheet()
    if (!sheet) return
    const s = selectedCell.value
    if (!s) return
    const maxRow = Math.max(1, sheet.rows.length)
    const maxCol = Math.max(1, sheet.max_col || 1)
    const newRi = Math.max(0, Math.min(s.ri + dRi, maxRow - 1))
    const newCi = Math.max(0, Math.min(s.ci + dCi, maxCol - 1))
    selectedCell.value = { ri: newRi, ci: newCi }
    if (!shiftKey) {
      selectionAnchor.value = { ri: newRi, ci: newCi }
    }
  }

  const handleCellKeydown = (e: KeyboardEvent) => {
    const s = editCell.value || selectedCell.value
    if (!s) return

    if (e.key === 'Escape') {
      if (editCell.value) { endEdit(false); e.preventDefault() }
    } else if (e.key === 'Tab') {
      e.preventDefault()
      if (editCell.value) endEdit(true)
      moveSelection(0, e.shiftKey ? -1 : 1)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (editCell.value) endEdit(true)
      moveSelection(e.shiftKey ? -1 : 1, 0)
    } else if (e.key === 'ArrowUp') {
      if (editCell.value) return  // 编辑模式：让 contenteditable 处理光标移动
      e.preventDefault(); moveSelection(-1, 0, e.shiftKey)
    } else if (e.key === 'ArrowDown') {
      if (editCell.value) return  // 编辑模式：让 contenteditable 处理
      e.preventDefault(); moveSelection(1, 0, e.shiftKey)
    } else if (e.key === 'ArrowLeft') {
      if (editCell.value) return
      e.preventDefault(); moveSelection(0, -1, e.shiftKey)
    } else if (e.key === 'ArrowRight') {
      if (editCell.value) return
      e.preventDefault(); moveSelection(0, 1, e.shiftKey)
    } else if (e.key === 'Delete' || e.key === 'Backspace') {
      if (!editCell.value) { e.preventDefault(); clearCell() }
      // 编辑模式下让 contenteditable 处理
    } else if (e.ctrlKey && e.key === 'a') {
      // Ctrl+A 全选
      e.preventDefault()
      const sheet = getSheet()
      if (!sheet) return
      const maxRi = Math.max(0, sheet.rows.length - 1)
      const maxCi = Math.max(0, (sheet.max_col || 1) - 1)
      selectedCell.value = { ri: maxRi, ci: maxCi }
      selectionAnchor.value = { ri: 0, ci: 0 }
      closeContextMenu()
    } else if (e.ctrlKey && e.key === 'c') {
      e.preventDefault(); copySelection()
    } else if (e.ctrlKey && e.key === 'v') {
      e.preventDefault(); pasteToSelection()
    } else if (e.key === 'F2') {
      e.preventDefault()
      if (selectedCell.value && !editCell.value)
        startEdit(selectedCell.value.ri, selectedCell.value.ci)
    } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey && e.key !== ' ') {
      // 直接输入字符 → 进入编辑模式（空格不拦截，由 contenteditable 处理）
      if (!editCell.value) {
        e.preventDefault()
        const cellEl = document.querySelector<HTMLElement>(`[data-cell-display="${s.ri}-${s.ci}"]`)
        if (cellEl) {
          startEdit(s.ri, s.ci).then(() => {
            const editEl = document.querySelector<HTMLElement>(`[data-cell-edit="${s.ri}-${s.ci}"]`)
            if (editEl) { editEl.textContent = e.key }
          })
        }
      }
    }
  }

  // ========== 右键菜单 ==========

  const showContextMenu = (e: MouseEvent, ri: number, ci: number) => {
    e.preventDefault()
    e.stopPropagation()
    endEdit(true)
    selectCell(ri, ci, e.shiftKey)
    const menuW = 180, menuH = 280
    contextMenu.value = {
      show: true,
      x: Math.min(e.clientX, window.innerWidth - menuW),
      y: Math.min(e.clientY, window.innerHeight - menuH),
      ri, ci,
    }
  }

  const closeContextMenu = () => { contextMenu.value.show = false }

  // ========== 鼠标拖拽多选 ==========

  const startDragSelect = (ri: number, ci: number, e: MouseEvent) => {
    if (e.button !== 0) return  // 仅左键
    endEdit(true)
    isDragging.value = true
    dragDidMove.value = false
    selectionAnchor.value = { ri, ci }
    selectedCell.value = { ri, ci }
    closeContextMenu()
    const sheet = getSheet()
    if (sheet && sheet.rows[ri] && sheet.rows[ri][ci]) {
      editingFormula.value = sheet.rows[ri][ci].f || sheet.rows[ri][ci].v
    } else {
      editingFormula.value = ''
    }
  }

  const updateDragSelect = (ri: number, ci: number) => {
    if (!isDragging.value) return
    if (selectedCell.value?.ri !== ri || selectedCell.value?.ci !== ci) {
      dragDidMove.value = true
    }
    selectedCell.value = { ri, ci }
  }

  const endDragSelect = () => {
    isDragging.value = false
  }

  // ========== 追加 ==========

  const addRow = () => {
    if (!excelData.value) return
    pushUndo()
    const sheet = excelData.value.sheets[excelData.value.activeSheet]
    sheet.rows.push(Array.from({ length: sheet.max_col || 1 }, () => emptyCell()))
    sheet.max_row = sheet.rows.length
  }

  const addCol = () => {
    if (!excelData.value) return
    pushUndo()
    const sheet = excelData.value.sheets[excelData.value.activeSheet]
    sheet.max_col = (sheet.max_col || 1) + 1
    for (const row of sheet.rows) row.push(emptyCell())
  }

  // ========== 保存 & 重置 ==========

  const saveToFile = async (doc: DocRecord): Promise<string> => {
    if (!excelData.value) throw new Error('Excel 数据未加载')
    endEdit(true)
    const saveRes = await axios.post(apiUrl('/api/excel/save'), { sheets: excelData.value.sheets })
    if (!saveRes.data.success) throw new Error(saveRes.data.message || 'Excel 保存接口返回失败')
    if (!saveRes.data.data_uri) throw new Error('保存后未获取到文件数据')
    return saveRes.data.data_uri
  }

  const initEmpty = () => {
    const emptyRow = Array.from({ length: 5 }, () => emptyCell())
    excelData.value = {
      sheets: [{ name: 'Sheet1', rows: [emptyRow], max_row: 1, max_col: 5 }],
      activeSheet: 0,
    }
    sheetStates.value = {}
    selectedCell.value = null
    selectionAnchor.value = null
    editCell.value = null
    colWidths.value = {}
    undoStack.value = []
  }

  // ========== 列宽拖拽 ==========

  const startColResize = (ci: number, e: MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const startX = e.clientX
    const startW = colWidths.value[ci] || 70
    const onMove = (ev: MouseEvent) => {
      colWidths.value[ci] = Math.max(30, startW + (ev.clientX - startX))
    }
    const onUp = () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }

  const reset = () => {
    excelData.value = null
    excelFilePath.value = ''
    selectedCell.value = null
    selectionAnchor.value = null
    editCell.value = null
    contextMenu.value = { show: false, x: 0, y: 0, ri: -1, ci: -1 }
    isDragging.value = false
    dragDidMove.value = false
    colWidths.value = {}
    editingFormula.value = ''
    undoStack.value = []
    redoStack.value = []
    sheetStates.value = {}
  }

  return {
    excelData, excelFilePath, excelFillColor, excelTextColor, selectedCell, selectionAnchor,
    editCell, copiedData, contextMenu,
    colWidths, editingFormula, undoStack, redoStack, excelLoading,
    selectedRange, isInRange, isActiveCell,
    loadExcelData, updateCell,
    addRow, addCol, clearCell,
    insertRowAbove, insertRowBelow, insertColLeft, insertColRight,
    deleteRow, deleteCol, moveSelection, selectCell,
    handleCellKeydown, showContextMenu, closeContextMenu,
    isDragging, startDragSelect, updateDragSelect, endDragSelect,
    saveToFile, initEmpty, reset,
    undo, redo, commitFormula, cancelEdit, startColResize, switchSheet,
    startEdit, endEdit, isEditing,
    copySelection, pasteToSelection, applyColorToSelection,
    toggleBold, toggleItalic, toggleUnderline, toggleStrikethrough,
    setCellFontSize, setCellFontFamily, setCellTextColor, setCellTextAlign,
    clearCellFormat,
  }
}
