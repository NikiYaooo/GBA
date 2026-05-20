import { describe, it, expect } from 'vitest'
import { parseHtmlSections } from './doc-sections'

describe('parseHtmlSections', () => {
  it('空文档返回空数组', () => {
    expect(parseHtmlSections('')).toEqual([])
  })

  it('解析 h2/h3 章节', () => {
    const html = '<h2>背景</h2><p>内容</p><h2>规则</h2><p>规则内容</p><h3>子规则</h3><p>细节</p>'
    const sections = parseHtmlSections(html)
    expect(sections).toHaveLength(3)
    expect(sections[0].title).toBe('背景')
    expect(sections[1].title).toBe('规则')
    expect(sections[2].title).toBe('子规则')
  })

  it('无标题返回空数组', () => {
    expect(parseHtmlSections('<p>纯文本</p>')).toEqual([])
  })
})
