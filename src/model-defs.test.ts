import { describe, it, expect } from 'vitest'
import { TEXT_MODELS, IMAGE_MODELS, DEFAULT_TEXT_MODEL, DEFAULT_IMAGE_MODEL } from './model-defs'

describe('TEXT_MODELS', () => {
  it('应该包含所有文本模型', () => {
    const names = TEXT_MODELS.map(m => m.name)
    expect(names).toContain('DeepSeek')
    expect(names).toContain('豆包')
    expect(names).toContain('GPT')
    expect(names).toContain('Gemini')
    expect(names).toContain('Kimi')
    expect(names).toContain('GLM')
    expect(names).toContain('Ollama (本地)')
  })

  it('每个模型都有 type 字段', () => {
    for (const m of TEXT_MODELS) {
      expect(['cloud', 'local']).toContain(m.type)
    }
  })
})

describe('IMAGE_MODELS', () => {
  it('应该包含所有图片模型，不含假模型', () => {
    const names = IMAGE_MODELS.map(m => m.name)
    expect(names).toContain('GPT-Image 2')
    expect(names).toContain('Qwen-Image 2')
    expect(names).toContain('豆包Seedream')
    expect(names).toContain('Stable Diffusion（本地）')
    expect(names).not.toContain('Midjourney')
    expect(names).not.toContain('Google Banana')
  })

  it('每个模型都有 type 字段', () => {
    for (const m of IMAGE_MODELS) {
      expect(['cloud', 'local']).toContain(m.type)
    }
  })
})

describe('default models', () => {
  it('DEFAULT_TEXT_MODEL 在 TEXT_MODELS 中', () => {
    expect(TEXT_MODELS.some(m => m.name === DEFAULT_TEXT_MODEL)).toBe(true)
  })

  it('DEFAULT_IMAGE_MODEL 在 IMAGE_MODELS 中', () => {
    expect(IMAGE_MODELS.some(m => m.name === DEFAULT_IMAGE_MODEL)).toBe(true)
  })
})
