import { apiClient } from "@/lib/apiClient"

export const guardrailService = {
  list: (limit = 50, offset = 0, q = "") => {
    let endpoint = `/api/guardrails?limit=${limit}&offset=${offset}`
    if (q) {
      endpoint += `&q=${encodeURIComponent(q)}`
    }
    return apiClient.get(endpoint)
  },
  
  create: (guardrailData) => {
    return apiClient.post("/api/guardrails", guardrailData)
  },
  
  update: (guardrailId, guardrailData) => {
    return apiClient.put(`/api/guardrails/${guardrailId}`, guardrailData)
  },
  
  delete: (guardrailId) => {
    return apiClient.delete(`/api/guardrails/${guardrailId}`)
  }
}
