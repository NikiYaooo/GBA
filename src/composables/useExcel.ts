import { ref } from 'vue'
import axios from 'axios'
import { apiUrl } from '@/utils/api'
import type { DocRecord, ExcelState, ApiResponse } from '@/types'

export function useExcel() {
  const excelData = ref<ExcelState | null>(null)
  const excelFilePath = ref('')
  const excelFillColor = ref('#ffffff')

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

  const updateCell = (sheetIdx: number, ri: number, ci: number, value: string) => {
    if (!excelData.value || !excelData.value.sheets[sheetIdx]) return
    const sheet = excelData.value.sheets[sheetIdx]
    if (!sheet.rows[ri]) sheet.rows[ri] = []
    if (!sheet.rows[ri][ci]) sheet.rows[ri][ci] = { v: '', f: '' }
    sheet.rows[ri][ci].v = value
    sheet.rows[ri][ci].f = ''
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
  }

  return {
    excelData, excelFilePath, excelFillColor,
    loadExcelData, updateCell, addRow, addCol, saveToFile, initEmpty, reset
  }
}
