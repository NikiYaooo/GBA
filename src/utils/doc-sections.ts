export interface DocSection {
  title: string
  level: number
  contentHtml: string
  contentText: string
}

/**
 * 将 HTML 文档按 h2/h3 标题解析为章节列表。
 */
export function parseHtmlSections(html: string): DocSection[] {
  if (!html) return []
  const pattern = /<h([23])(?:\s+[^>]*)?>(.*?)<\/h\1>/gi
  const matches: { level: number; title: string; start: number; end: number }[] = []
  let match
  while ((match = pattern.exec(html)) !== null) {
    const title = match[2].replace(/<[^>]+>/g, '').trim()
    matches.push({
      level: parseInt(match[1]),
      title,
      start: match.index + match[0].length,
      end: match.index + match[0].length,
    })
  }
  if (matches.length === 0) return []
  for (let i = 0; i < matches.length; i++) {
    if (i + 1 < matches.length) {
      matches[i].end = matches[i + 1].start
    } else {
      matches[i].end = html.length
    }
  }
  return matches.map(m => {
    const contentHtml = html.slice(m.start, m.end).trim()
    return {
      title: m.title,
      level: m.level,
      contentHtml,
      contentText: contentHtml.replace(/<[^>]+>/g, '').trim(),
    }
  })
}

/**
 * 在 TipTap 编辑器中替换指定章节内容。
 */
export function replaceSectionInEditor(editor: any, section: DocSection, newHtml: string): void {
  let found = false
  editor.state.doc.forEach((node: any, offset: number) => {
    if (found) return false
    if (node.type.name === 'heading' && node.textContent.trim() === section.title) {
      found = true
      let endPos = offset + node.nodeSize
      let nextFound = false
      editor.state.doc.forEach((n: any, pos: number) => {
        if (nextFound) return false
        if (pos > offset && n.type.name === 'heading' && (n.attrs.level === 2 || n.attrs.level === 3)) {
          endPos = pos
          nextFound = true
          return false
        }
        return true
      })
      editor.chain().focus().deleteRange({ from: offset, to: endPos }).insertContentAt(offset, `<h2>${section.title}</h2>${newHtml}`).run()
    }
  })
}

/**
 * 获取光标所在的当前章节。
 */
export function getCurrentSection(editor: any, sections: DocSection[], html: string): DocSection | null {
  if (!editor || sections.length === 0) return null
  const { from } = editor.state.selection
  let currentSection: DocSection | null = null
  editor.state.doc.forEach((node: any, pos: number) => {
    if (node.type.name === 'heading' && (node.attrs.level === 2 || node.attrs.level === 3)) {
      const s = sections.find(s => s.title === node.textContent.trim())
      if (s && pos <= from) {
        currentSection = s
      }
    }
  })
  return currentSection
}
