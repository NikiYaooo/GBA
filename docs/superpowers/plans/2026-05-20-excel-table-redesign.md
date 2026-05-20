# Excel 表格编辑模式重构实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 重构 Excel 表格编辑模式，使其交互完全参照 Microsoft Excel，同时将 Word 文档工具栏的功能接入到表格编辑中。

**架构：** 在现有 `useExcel.ts` composable + `HomePage.vue` 模板上增量增强。单元格数据增加格式字段（bold/italic/fontSize 等），工具栏按钮变为上下文感知（Excel 模式分发到 composable 方法）。后端 excel.py 的 save 端点同步写入格式到 xlsx。

**技术栈：** Vue 3 + TypeScript + openpyxl

---

## 文件结构

| 文件 | 职责 | 变更类型 |
|---|---|---|
| `src/types/index.ts:35-39` | `CellData` 类型定义 | 修改 — 增加格式字段 |
| `src/composables/useExcel.ts` | Excel 表格核心逻辑（数据、公式、选区、格式操作） | 修改 — 新增格式方法、交互优化 |
| `src/pages/HomePage.vue` | 工具栏分发逻辑 + 单元格渲染模板 | 修改 — 模式感知 + 内联样式 |
| `api/routers/excel.py` | Excel 文件解析和保存 | 修改 — 读取/写入格式到 xlsx |

---

### 任务 1：扩展 CellData 类型 + 格式操作方法

**文件：**
- 修改：`src/types/index.ts:35-39`
- 修改：`src/composables/useExcel.ts:320-336`（writeCell）、`src/composables/useExcel.ts:383-397`（clearCell）、`src/composables/useExcel.ts:484-527`（行列插入）

- [ ] **步骤 1：扩展 CellData 类型**

```typescript
// src/types/index.ts
export interface CellData {
  v: string
  f: string
  color?: string
  bold?: boolean
  italic?: boolean
  underline?: boolean
  strikethrough?: boolean
  fontSize?: number
  fontFamily?: string
  textColor?: string
  textAlign?: 'left' | 'center' | 'right'
}
```

- [ ] **步骤 2：让 writeCell 在写入时保留格式字段**

当前 `writeCell`（第 320 行）在创建新单元格时用 `{ v: '', f: '' }`，在已有单元格上只修改 `v`/`f`。不需要改动 — 因为已存在的 cell 对象保留原属性，新单元格用 `{ v: '', f: '' }` 也正确（格式字段为 undefined）。

但为了后续方法能正确创建单元格，需要一个创建空单元格的辅助函数。在 `writeCell` 前（约 319 行）添加：

```typescript
function emptyCell(): CellData {
  return { v: '', f: '' }
}
```

- [ ] **步骤 3：替换所有 `{ v: '', f: '' }` 字面量为 `emptyCell()`**

需要替换的位置（共 5 处）：
- `insertRowAbove`（第 490 行）：`Array.from({ length: sheet.max_col || 1 }, () => ({ v: '', f: '' }))` → `emptyCell()`
- `insertRowBelow`（第 502 行）：同上
- `insertColLeft`（第 515 行）：`row.splice(s.ci, 0, { v: '', f: '' })` → `emptyCell()`
- `insertColRight`（第 526 行）：同上
- `pasteToSelection`（第 442 行附近）：`sheet.rows[targetRi].push({ v: '', f: '' })` → `emptyCell()`

- [ ] **步骤 4：修改 clearCell 保留新建单元格走 emptyCell**

`clearCell`（第 383-397 行）重置单元格为 `{ v: '', f: '' }`，这已经清除了格式字段（因为重新赋值整个对象），这正是期望行为 — 清除应该连格式一起清除。

不需要改动。

- [ ] **步骤 5：添加所有格式操作方法**

在 `useExcel.ts` 中 `endEdit` / `commitFormula` 区域之后（约 348 行后），`updateCell` 之前，添加以下方法：

```typescript
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
```

- [ ] **步骤 6：将新方法添加到 return 语句**

在 `useExcel.ts` 的 return（约 719-733 行）中添加：

```typescript
return {
  // ... 现有 ...
  toggleBold, toggleItalic, toggleUnderline, toggleStrikethrough,
  setCellFontSize, setCellFontFamily, setCellTextColor, setCellTextAlign,
  clearCellFormat,
}
```

确保这些方法在 `copySelection` 之前导出，以便在 return 语句中有序排列。

---

### 任务 2：工具栏上下文感知分发

**文件：**
- 修改：`src/pages/HomePage.vue:361-394`（工具栏动作函数）
- 修改：`src/pages/HomePage.vue:975-1050`（工具栏模板）

- [ ] **步骤 1：添加 `isExcelMode` computed**

在 `src/pages/HomePage.vue` script 区中，约在 `const isBold = () => ...` 附近（第 382 行后）添加：

```typescript
const isExcelMode = computed(() => !!excel.excelData.value)
```

- [ ] **步骤 2：修改工具栏动作函数为模式感知**

将第 362-381 行的工具栏函数改为：

```typescript
const toggleBold = () => {
  if (isExcelMode.value) excel.toggleBold()
  else tiptapEditor.value?.chain().focus().toggleBold().run()
}
const toggleItalic = () => {
  if (isExcelMode.value) excel.toggleItalic()
  else tiptapEditor.value?.chain().focus().toggleItalic().run()
}
const toggleUnderline = () => {
  if (isExcelMode.value) excel.toggleUnderline()
  else tiptapEditor.value?.chain().focus().toggleUnderline().run()
}
const toggleStrikethrough = () => {
  if (isExcelMode.value) excel.toggleStrikethrough()
  else tiptapEditor.value?.chain().focus().toggleStrike().run()
}
const setFontSize = (size: string) => {
  if (isExcelMode.value) excel.setCellFontSize(parseInt(size))
  else { fontSize.value = size; tiptapEditor.value?.chain().focus().setMark('textStyle', { fontSize: size }).run() }
}
const setFontFamily = (font: string) => {
  if (isExcelMode.value) excel.setCellFontFamily(font)
  else tiptapEditor.value?.chain().focus().setFontFamily(font).run()
}
const setColor = (color: string) => {
  if (isExcelMode.value) excel.setCellTextColor(color)
  else { fontColor.value = color; tiptapEditor.value?.chain().focus().setColor(color).run() }
}
const setHighlight = (color: string) => {
  if (isExcelMode.value) { excel.excelFillColor.value = color; excel.applyColorToSelection() }
  else { highlightColor.value = color; tiptapEditor.value?.chain().focus().setHighlight({ color }).run() }
}
const setAlign = (align: string) => {
  if (isExcelMode.value) excel.setCellTextAlign(align as 'left' | 'center' | 'right')
  else tiptapEditor.value?.chain().focus().setTextAlign(align).run()
}
const clearMarks = () => {
  if (isExcelMode.value) excel.clearCellFormat()
  else tiptapEditor.value?.chain().focus().clearNodes().unsetAllMarks().run()
}
// undo 和 redo 也要改
const undoAction = () => {
  if (isExcelMode.value) excel.undo()
  else tiptapEditor.value?.chain().focus().undo().run()
}
const redoAction = () => {
  if (isExcelMode.value) { /* Excel 无重做，可忽略或保留空 */ }
  else tiptapEditor.value?.chain().focus().redo().run()
}
```

- [ ] **步骤 3：更新模板中的方法绑定**

模板中（第 978-979 行） `@click="undo"` 改为 `@click="undoAction"`，`@click="redo"` 改为 `@click="redoAction"`：

```html
<button class="p-1.5 rounded hover:bg-app-hover" @click="undoAction" title="撤销"><Undo class="w-3.5 h-3.5" /></button>
<button class="p-1.5 rounded hover:bg-app-hover" @click="redoAction" title="重做"><Redo class="w-3.5 h-3.5" /></button>
```

- [ ] **步骤 4：文档专用按钮添加 v-if 隐藏**

在模板中（第 1008-1050 行），为以下按钮包裹 `v-if="!isExcelMode"`：
- 标题行（H1/H2/H3 第 1009-1011 行）
- 引用按钮（第 1012 行）
- 代码块按钮（第 1013 行）
- 列表按钮（第 1015-1016 行）
- 插入图片/表格/分割线（第 1022-1024 行）

将第二行工具栏用一个外层 `template v-if` 包裹：

```html
<template v-if="!isExcelMode">
  <div class="px-4 py-1 flex items-center gap-0.5 flex-wrap">
    <!-- H1/H2/H3/引用/代码块/列表/对齐/插入 -->
  </div>
</template>
<template v-else>
  <div class="px-4 py-1 flex items-center gap-0.5 flex-wrap">
    <!-- Excel 模式第二行：仅对齐按钮（对齐在 Excel 中有意义） -->
    <button class="p-1.5 rounded hover:bg-app-hover" @click="setAlign('left')" title="左对齐"><AlignLeft class="w-4 h-4" /></button>
    <button class="p-1.5 rounded hover:bg-app-hover" @click="setAlign('center')" title="居中"><AlignCenter class="w-4 h-4" /></button>
    <button class="p-1.5 rounded hover:bg-app-hover" @click="setAlign('right')" title="右对齐"><AlignRight class="w-4 h-4" /></button>
  </div>
</template>
```

- [ ] **步骤 5：确认 `isBold()` 等激活态函数在 Excel 模式下不报错**

`isBold()`（第 382 行）调用 `tiptapEditor.value?.isActive('bold')`，当 `tiptapEditor` 为 null 时返回 undefined（`?.` 保护），不会报错。不需要改动。

---

### 任务 3：交互模型优化

**文件：**
- 修改：`src/composables/useExcel.ts:580-621`（handleCellKeydown）
- 修改：`src/composables/useExcel.ts:567-578`（moveSelection）
- 修改：`src/composables/useExcel.ts:300-316`（selectCell）

- [ ] **步骤 1：修复 handleCellKeydown 的 Enter/Escape/方向键行为**

将 `handleCellKeydown`（第 580-621 行）替换为：

```typescript
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
    if (editCell.value) {
      // 编辑模式：让 contenteditable 处理光标移动
      return
    }
    e.preventDefault(); moveSelection(-1, 0)
  } else if (e.key === 'ArrowDown') {
    if (editCell.value) {
      return  // 编辑模式：让 contenteditable 处理
    }
    e.preventDefault(); moveSelection(1, 0)
  } else if (e.key === 'ArrowLeft') {
    if (editCell.value) return
    e.preventDefault(); moveSelection(0, -1)
  } else if (e.key === 'ArrowRight') {
    if (editCell.value) return
    e.preventDefault(); moveSelection(0, 1)
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
  } else if (e.ctrlKey && e.key === 'c') {
    e.preventDefault(); copySelection()
  } else if (e.ctrlKey && e.key === 'v') {
    e.preventDefault(); pasteToSelection()
  } else if (e.key === 'F2') {
    e.preventDefault()
    if (selectedCell.value && !editCell.value)
      startEdit(selectedCell.value.ri, selectedCell.value.ci)
  } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
    // 直接输入字符 → 进入编辑模式
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
```

- [ ] **步骤 2：添加 `selectCell` 的 Shift 扩展**

当前 `selectCell`（第 300 行）已支持 `shiftKey` 参数。确认其正确性：

```typescript
// 保持现有代码不变，验证逻辑：
// 第 302 行：if (shiftKey && selectionAnchor.value) 时扩展选区
// 否则重置 anchor 为新位置
```

- [ ] **步骤 3：确认 Edit 模式下 Enter 不触发 handleCellKeydown**

编辑模式的 contenteditable div 阻止 Enter 冒泡到全局处理函数。当前模板（HomePage.vue 第 1144 行）有：

```html
@keydown.enter.prevent="excelCellBlur($event); excel.moveSelection($event.shiftKey ? -1 : 1, 0)"
```

这会在 Enter 时 blur → `endEdit(true)` → moveSelection。这已经正确实现，不需要改动。

---

### 任务 4：单元格格式渲染

**文件：**
- 修改：`src/pages/HomePage.vue:1152-1155`（显示模式 div）

- [ ] **步骤 1：显示模式 div 添加内联样式**

将显示模式 div（约第 1152 行）：

```html
<div v-else :data-cell-display="`${ri}-${ci}`" class="p-1 min-h-[26px] text-xs select-none">
  <span v-if="cell.f" class="text-blue-500 font-mono" :title="'公式: '+cell.f">{{ cell.v }}</span>
  <span v-else>{{ cell.v || ' ' }}</span>
</div>
```

改为：

```html
<div v-else :data-cell-display="`${ri}-${ci}`" class="p-1 min-h-[26px] text-xs select-none"
  :style="{
    fontWeight: cell.bold ? 'bold' : undefined,
    fontStyle: cell.italic ? 'italic' : undefined,
    textDecoration: cell.underline ? 'underline' : cell.strikethrough ? 'line-through' : undefined,
    fontSize: cell.fontSize ? cell.fontSize + 'px' : undefined,
    fontFamily: cell.fontFamily || undefined,
    color: cell.textColor || undefined,
    textAlign: cell.textAlign || undefined,
    background: cell.color || undefined
  }"
>
  <span v-if="cell.f" class="text-blue-500 font-mono" :title="'公式: '+cell.f">{{ cell.v }}</span>
  <span v-else>{{ cell.v || ' ' }}</span>
</div>
```

---

### 任务 5：Excel 文件格式兼容

**文件：**
- 修改：`api/routers/excel.py:54-99`（save 端点）
- 修改：`api/routers/excel.py:10-51`（parse 端点，读取格式）

- [ ] **步骤 1：save 端点在生成 xlsx 时写入格式**

在 `api/routers/excel.py` save 端点（第 80-88 行）的颜色写入之后，添加字体格式和文本对齐的写入：

```python
# 在 color 写入之后（第 88 行 cell.border 之前），添加：
bold = cell_data.get("bold", False)
italic = cell_data.get("italic", False)
underline = cell_data.get("underline", False)
strikethrough = cell_data.get("strikethrough", False)
font_size = cell_data.get("fontSize")
font_family = cell_data.get("fontFamily")
text_color = cell_data.get("textColor")

if any([bold, italic, underline, strikethrough, font_size, font_family, text_color]):
    font_kwargs = {}
    if bold: font_kwargs["bold"] = True
    if italic: font_kwargs["italic"] = True
    if underline: font_kwargs["underline"] = "single"
    if strikethrough: font_kwargs["strike"] = True
    if font_size: font_kwargs["size"] = font_size
    if font_family: font_kwargs["name"] = font_family
    if text_color: font_kwargs["color"] = text_color.lstrip('#')
    if font_kwargs:
        cell.font = Font(**font_kwargs)

text_align = cell_data.get("textAlign")
if text_align:
    cell.alignment = Alignment(horizontal=text_align, vertical='center')
```

- [ ] **步骤 2：parse 端点从 xlsx 读取格式**

在 `api/routers/excel.py` parse 端点（第 36-39 行的 `row_data.append` 处），添加读取单元格样式：

```python
# 在第 36 行 row_data.append({...}) 之前，添加样式读取：
cell_style = {}
if cell.font:
    if cell.font.bold: cell_style["bold"] = True
    if cell.font.italic: cell_style["italic"] = True
    if cell.font.underline and cell.font.underline != 'none': cell_style["underline"] = True
    if cell.font.strike: cell_style["strikethrough"] = True
    if cell.font.size: cell_style["fontSize"] = cell.font.size
    if cell.font.name: cell_style["fontFamily"] = cell.font.name
    if cell.font.color and cell.font.color.rgb:
        cell_style["textColor"] = "#" + str(cell.font.color.rgb)
if cell.fill and cell.fill.start_color and cell.fill.start_color.rgb:
    rgb = str(cell.fill.start_color.rgb)
    if rgb and rgb != '00000000':
        cell_style["color"] = "#" + rgb[-6:] if len(rgb) >= 6 else "#" + rgb
if cell.alignment and cell.alignment.horizontal:
    cell_style["textAlign"] = cell.alignment.horizontal

row_data.append({
    "v": str(computed_val) if computed_val is not None else "",
    "f": formula,
    **cell_style
})
```

---

### 任务 6：验证构建

- [ ] **步骤 1：TypeScript 类型检查**

运行：`npx vue-tsc -b`
预期：无错误

- [ ] **步骤 2：运行 Python 测试**

运行：`.venv\Scripts\python.exe -m pytest tests/ -v`
预期：全部通过（44 个测试）

- [ ] **步骤 3：Vite 构建**

运行：`npx vite build`
预期：构建成功

- [ ] **步骤 4：完整 electron-builder 构建**

运行：`npm run build`
预期：构建成功，release28/ 中生成 portable exe
