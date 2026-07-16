import { http } from './http'

export interface InsightMessage {
  id: number; scenic_area_id: number; normalized_question: string | null; primary_topic: string | null
  intent: string | null; sentiment: 'positive' | 'neutral' | 'negative' | null; sentiment_score: number | null
  issue_type: string | null; needs_attention: boolean; resolution_status: 'resolved' | 'unresolved'
  analysis_status: 'pending' | 'processing' | 'completed' | 'failed'; analysis_attempts: number
  error_message: string | null; question: string | null; answer: string | null; created_at: string
}
export interface InsightPage { items: InsightMessage[]; page: number; page_size: number; total: number }
export interface InsightReport {
  id: number; scenic_area_id: number; period_type: 'daily' | 'weekly'; period_start: string; period_end: string
  metrics_snapshot: Record<string, unknown>; summary: string | null; attention_points: string[] | null
  risk_findings: string[] | null; recommendations: string[] | null
  generation_status: 'pending' | 'processing' | 'completed' | 'failed'; generation_model: string | null
  error_message: string | null; generated_at: string | null; created_at: string
}

export const insightsApi = {
  listMessages: (params: Record<string, string | number | boolean | undefined>) => http.get<InsightPage>('/admin/insights/messages', { params }),
  retry: (id: number) => http.post(`/admin/insights/messages/${id}/retry`),
  retryFailed: (scenicAreaId: number) => http.post('/admin/insights/messages/retry-failed', undefined, { params: { scenic_area_id: scenicAreaId } }),
  resolve: (id: number, resolved = true) => http.patch(`/admin/insights/messages/${id}/resolve`, { resolved }),
  createReport: (data: { scenic_area_id: number; period_type: 'daily' | 'weekly'; period_start: string; period_end: string }) => http.post<InsightReport>('/admin/insight-reports', data),
  listReports: (scenicAreaId: number) => http.get<InsightReport[]>('/admin/insight-reports', { params: { scenic_area_id: scenicAreaId } }),
  getReport: (id: number) => http.get<InsightReport>(`/admin/insight-reports/${id}`),
}
