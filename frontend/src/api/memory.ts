import { jsonRequest } from '@/api/client'
import type { AppInfo, MemorySearchResponse, MemoryStats } from '@/types/api'

export function fetchInfo(): Promise<AppInfo> {
  return jsonRequest<AppInfo>('/info')
}

export function fetchMemoryStats(): Promise<MemoryStats> {
  return jsonRequest<MemoryStats>('/memory/stats')
}

export function searchMemory(query: string, top_k = 12, conversation_id?: string): Promise<MemorySearchResponse> {
  return jsonRequest<MemorySearchResponse>('/memory/search', {
    method: 'POST',
    body: JSON.stringify({ query, top_k, conversation_id }),
  })
}

export function pauseWriteback(): Promise<{ status: string }> {
  return jsonRequest('/memory/writeback/pause', { method: 'POST' })
}

export function resumeWriteback(): Promise<{ status: string }> {
  return jsonRequest('/memory/writeback/resume', { method: 'POST' })
}

export function deleteMemory(table: string, id: string): Promise<{ status: string }> {
  const encoded = encodeURIComponent(id)
  return jsonRequest(`/memory/${table}/${encoded}`, { method: 'DELETE' })
}
