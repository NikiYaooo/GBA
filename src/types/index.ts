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
  chunk_size_min?: number
  chunk_size_max?: number
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
  qualityCheckPrompt?: string
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
  openAfterUpdate?: boolean
}

export interface NavConfig {
  id: string
  name: string
  path: string
}

export interface Reminder {
  id: string
  content: string
  month: number | null
  day: number | null
  hour: number
  minute: number
  enabled: boolean
  created_at?: number
}

export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  message?: string
}

// ========== 知识库 v2.6.2 类型 ==========

export interface KBProject {
  id: string
  name: string
  description?: string
  type: 'personal' | 'team'
  embedding_model: string
  chunk_size_min: number
  chunk_size_max: number
  created_at: number
  updated_at: number
  archived: boolean
  doc_count?: number
}

export interface KBFolder {
  id: string
  name: string
  created_at: number
}

export interface KBDocumentV2 {
  id: string
  file_hash: string
  filename: string
  doc_type: string
  file_size: number
  folder_id: string
  note: string
  added_at: number
  updated_at: number
  chunk_count: number
  vector_status: string
  status?: string
}

export interface KBSearchResult {
  content: string
  metadata?: Record<string, any>
  score: number
  project_name?: string
  project_id?: string
}

export interface KBBackup {
  filename: string
  size: number
  created_at: number
}
