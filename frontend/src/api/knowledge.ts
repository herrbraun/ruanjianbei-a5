import type { AxiosProgressEvent } from 'axios'

import { http } from './http'

export interface ScenicArea {
  id: number
  code: string
  name: string
  description: string | null
  is_enabled: boolean
}

export interface KnowledgeBase {
  id: number
  code: string
  name: string
  description: string | null
  is_enabled: boolean
}

export interface ProfileBinding {
  id: number
  knowledge_base_id: number
  is_enabled: boolean
  retrieval_priority: number
  knowledge_base: KnowledgeBase | null
}

export interface RagProfile {
  id: number
  scenic_area_id: number
  name: string
  status: 'draft' | 'active' | 'archived'
  embedding_model: string
  embedding_dimensions: number
  top_k: number
  rerank_model: string | null
  knowledge_base_bindings: ProfileBinding[]
}

export interface KnowledgeDocument {
  id: number
  knowledge_base_id: number
  original_filename: string
  mime_type: string
  content_hash: string
  source_priority: number
  status: 'pending' | 'indexing' | 'indexed' | 'failed'
  error_message: string | null
  chunk_count: number
  embedding_count: number
  created_at: string
  indexed_at: string | null
}

export interface RagHit {
  chunk_id: number
  document_id: number
  knowledge_base_id: number
  knowledge_base_name: string
  source_priority: number
  score: number
  spot_id: string | null
  spot_name: string | null
  section: string | null
  source_locator: string | null
  content: string
}

export interface RagSearchResult {
  scenic_area_code: string
  rag_profile_id: number
  rag_profile_name: string
  knowledge_bases: string[]
  hits: RagHit[]
}

export interface RagSearchPreviewResult extends RagSearchResult {
  ai_answer: string | null
  answer_model: string | null
  answer_duration_ms: number | null
  answer_status: 'success' | 'failed'
  answer_error: string | null
}

export const knowledgeApi = {
  listScenicAreas: () => http.get<ScenicArea[]>('/admin/scenic-areas'),
  createScenicArea: (data: Omit<ScenicArea, 'id'>) => http.post<ScenicArea>('/admin/scenic-areas', data),
  listKnowledgeBases: () => http.get<KnowledgeBase[]>('/admin/knowledge-bases'),
  createKnowledgeBase: (data: Omit<KnowledgeBase, 'id'>) => http.post<KnowledgeBase>('/admin/knowledge-bases', data),
  listProfiles: (scenicAreaId?: number) => http.get<RagProfile[]>('/admin/rag-profiles', { params: { scenic_area_id: scenicAreaId } }),
  createProfile: (data: {
    scenic_area_id: number
    name: string
    status: 'draft' | 'active'
    top_k: number
    knowledge_bases: Array<{ knowledge_base_id: number; is_enabled: boolean; retrieval_priority: number }>
  }) => http.post<RagProfile>('/admin/rag-profiles', data),
  activateProfile: (id: number) => http.post<RagProfile>(`/admin/rag-profiles/${id}/activate`),
  listDocuments: (knowledgeBaseId?: number) => http.get<KnowledgeDocument[]>('/admin/knowledge/documents', { params: { knowledge_base_id: knowledgeBaseId } }),
  uploadDocument: (data: FormData, onUploadProgress?: (event: AxiosProgressEvent) => void) =>
    http.post<KnowledgeDocument>('/admin/knowledge/documents', data, { onUploadProgress }),
  reindexDocument: (id: number) => http.post<KnowledgeDocument>(`/admin/knowledge/documents/${id}/index`),
  deleteDocument: (id: number) => http.delete<void>(`/admin/knowledge/documents/${id}`),
  previewSearch: (data: { scenic_area_id: number; rag_profile_id: number; query: string; top_k?: number }) => http.post<RagSearchPreviewResult>('/admin/rag/search-preview', data),
  listPublicScenicAreas: () => http.get<ScenicArea[]>('/scenic-areas'),
  search: (data: { scenic_area_code: string; query: string; top_k?: number }) => http.post<RagSearchResult>('/rag/search', data),
}
