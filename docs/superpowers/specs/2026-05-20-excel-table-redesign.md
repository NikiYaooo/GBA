# Excel 表格编辑模式重构设计规格

## 概述

重构现有 Excel 表格编辑模式，使其交互完全参照 Microsoft Excel，同时将 Word 文档工具栏的功能接入到表格编辑中。

## 架构

**方案：增量增强（保持现有架构）**

在现有 `useExcel.ts` composable + `HomePage.vue` 模板结构上扩展：
- 单元格数据增加格式字段
- 工具栏按钮变更为上下文感知（Excel 模式分发到 composable 方法）
- 不抽取独立组件，不改动 HomePage.vue 主体结构

**技术栈：** Vue 3 (Composition API) + TypeScript + openpyxl (Python 保存)

## 数据模型

### 单元格类型扩展

```typescript
interface CellData {
  v: string           // 显示值
  f: string           // 公式（=开头）
  color?: string      // 单元格背景色
  // 以下为新增格式字段
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

所有字段保持原始类型，兼容 JSON.stringify 序列化（撤销栈、文件保存）。

## 工具栏集成

### 模式感知分发

`HomePage.vue` 中的工具栏按钮由当前模式决定行为：

```
isExcelMode = computed(() => !!excel.excelData.value)

toggleBold() => isExcelMode ? excel.toggleBold() : tiptapEditor.value?.chain().focus().toggleBold().run()
```

### 按钮映射

| 工具栏按钮 | Excel 模式行为 |
|---|---|
| 撤销 | `excel.undo()` |
| 字体/字号 | 设置选中单元格 fontFamily / fontSize |
| 加粗/斜体/下划线/删除线 | 切换选中单元格 boolean 标志 |
| 文字颜色 | 设置选中单元格 textColor |
| 高亮 | 设置选中单元格 color（背景色） |
| 对齐（左/中/右） | 设置选中单元格 textAlign |
| 清除格式 | 清除选中单元格所有格式字段 |
| H1/H2/H3/引用/代码块/列表 | Excel 模式隐藏 |
| 插入图片/表格/分割线 | Excel 模式隐藏 |

## 交互模型

### 选择模式（默认）

- **单击** → 选中单元格（蓝色边框）
- **方向键** → 单元格间移动选择
- **Shift + 方向键 / Shift + 点击** → 扩展选区
- **Ctrl + A** → 全选当前工作表
- **Tab** → 选中右侧单元格
- **Enter** → 选中下方单元格
- **Delete / Backspace** → 清空选中单元格内容
- **输入字符** → 进入编辑模式，原内容替换为输入的字符
- **F2** → 进入编辑模式，保留原内容

### 编辑模式（单元格内）

- **双击 / F2 / 输入字符** → 进入编辑
- **方向键** → 文本内移动光标
- **Enter** → 确认编辑，选中下方单元格
- **Tab** → 确认编辑，选中右侧单元格
- **Escape** → 取消编辑，恢复原值
- **点击其他单元格** → 确认编辑并切换选择

### 公式栏

- 选中单元格时显示内容（优先公式 f，其次值 v）
- 输入 `=` 开头视为公式，回车后计算
- 编辑模式下与单元格内容保持同步

## 单元格渲染

### 显示模式

根据格式字段应用内联样式：

```
fontWeight: bold ? 'bold' : ''
fontStyle: italic ? 'italic' : ''
textDecoration: underline/strikethrough
fontSize / fontFamily / color / textAlign / background
```

### 编辑模式

纯文本 contenteditable，不显示格式标记（与 Excel 一致）。

## 文件保存兼容

`api/routers/excel.py` save 端点从单元格数据读取格式字段，通过 openpyxl 写入 xlsx：

- bold → Font(bold=True)
- color → PatternFill
- textAlign → Alignment(horizontal=...)
- fontSize → Font(size=...)
- fontFamily → Font(name=...)
- textColor → Font(color=...)

## 不包含范围

- 自动填充柄
- 条件格式
- 数据验证 / 下拉列表
- 合并单元格
- 冻结窗格
- 排序/筛选

## 任务分解

### 任务 1：扩展单元格数据模型

**文件：** `src/composables/useExcel.ts`

- writeCell 中保留现有格式字段，新建单元格时格式字段初始化为空
- initEmpty、addRow、addCol、insertRowAbove/Below、insertColLeft/Right 确保不丢失格式
- 验证 pushUndo/undo 序列化兼容

### 任务 2：Excel 格式操作方法

**文件：** `src/composables/useExcel.ts`

新增方法：

- `toggleBold()` — 遍历选区切换 bold
- `toggleItalic()` — 遍历选区切换 italic
- `toggleUnderline()` — 遍历选区切换 underline
- `toggleStrikethrough()` — 遍历选区切换 strikethrough
- `setCellFontSize(n: number)` — 设置选区 fontSize
- `setCellFontFamily(f: string)` — 设置选区 fontFamily
- `setCellTextColor(c: string)` — 设置选区 textColor
- `setCellTextAlign(a: string)` — 设置选区 textAlign
- `clearCellFormat()` — 清除选区所有格式（保留 v/f）

所有方法基于 `eachInRange` 遍历选区。

### 任务 3：工具栏上下文分发

**文件：** `src/pages/HomePage.vue`

- 新增 `isExcelMode` computed
- toggleBold / toggleItalic / toggleUnderline / toggleStrikethrough 改为模式感知
- setFontSize / setFontFamily / setColor / setHighlight / setAlign 改为模式感知
- undo / clearMarks 改为模式感知（Excel 时调 excel.undo / excel.clearCellFormat）
- 文档专用按钮添加 v-if="!isExcelMode"

### 任务 4：交互模型优化

**文件：** `src/composables/useExcel.ts` + `src/pages/HomePage.vue`

- Enter 在编辑模式下确认并下移，在选中模式下下移一格
- Escape 取消编辑恢复原值
- Shift+方向键扩展选区
- Ctrl+A 全选
- Delete/Backspace 选中模式清空选中单元格
- 编辑模式下方向键在文本内移动光标

### 任务 5：单元格格式渲染

**文件：** `src/pages/HomePage.vue` + `api/routers/excel.py`

- 显示模式 div 添加内联样式绑定，读取单元格格式字段
- 编辑模式 div 保持纯文本
- excel.py save 端点写入格式到 xlsx

### 任务 6：验证构建

- TypeScript 类型检查
- Python 测试
- npm run build
