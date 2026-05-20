import { describe, it, expect } from 'vitest'
import { apiUrl, setApiBaseUrl, getApiBaseUrl, getErrMsg } from './api'

describe('apiUrl', () => {
  it('应该拼接 URL', () => {
    setApiBaseUrl('http://127.0.0.1:8000')
    expect(apiUrl('/api/test')).toBe('http://127.0.0.1:8000/api/test')
  })

  it('缺少 / 时自动补全', () => {
    setApiBaseUrl('http://127.0.0.1:8000')
    expect(apiUrl('api/test')).toBe('http://127.0.0.1:8000/api/test')
  })
})

describe('setApiBaseUrl / getApiBaseUrl', () => {
  it('set 和 get 对应', () => {
    setApiBaseUrl('http://localhost:3000/')
    expect(getApiBaseUrl()).toBe('http://localhost:3000')
  })
})

describe('getErrMsg', () => {
  it('应该提取 response.data.detail', () => {
    const err = { response: { data: { detail: '模型配置错误' } } }
    expect(getErrMsg(err)).toBe('模型配置错误')
  })

  it('应该提取 response.data.message', () => {
    const err = { response: { data: { message: 'API Key 无效' } } }
    expect(getErrMsg(err)).toBe('API Key 无效')
  })

  it('应该提取 err.message', () => {
    const err = new Error('网络错误')
    expect(getErrMsg(err)).toBe('网络错误')
  })

  it('应该返回默认 fallback', () => {
    expect(getErrMsg(null)).toBe('未知错误')
  })

  it('字符串直接返回', () => {
    expect(getErrMsg('custom error')).toBe('custom error')
  })
})
