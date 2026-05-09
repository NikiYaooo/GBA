export interface DocRecord {
  id: string
  name: string
  type: string
  category: string
  path: string
  content: string
  created_at?: number
}

export interface ModelInfo {
  name: string
  type: 'cloud' | 'local'
  available?: boolean
}

export interface ModelConfig {
  modelId: string
  apiKey: string
}

export interface CategoryDef {
  id: string
  label: string
  icon: string
}

export interface SheetData {
  name: string
  rows: CellData[][]
  max_row: number
  max_col: number
}

export interface CellData {
  v: string
  f: string
  color?: string
}

export interface ExcelState {
  sheets: SheetData[]
  activeSheet: number
}

export interface KBStats {
  total_documents: number
  total_chunks: number
  total_size_bytes: number
  vector_count: number
  chunk_size?: number
  documents: KBDocument[]
}

export interface KBDocument {
  file_hash: string
  filename: string
  type: string
  version: string
  added_at: number
  file_size: number
  chunks_count: number
}

export interface Profession {
  id: string
  name: string
  role_count?: number
  roles?: Role[]
  prompts: PromptTemplate[]
}

export interface Role {
  id: string
  name: string
  prompt: string
}

export interface PromptTemplate {
  id: string
  name: string
  content: string
}

export interface SVNConfig {
  id: string
  name: string
  path: string
}

export interface NavConfig {
  id: string
  name: string
  path: string
}

export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  message?: string
}
