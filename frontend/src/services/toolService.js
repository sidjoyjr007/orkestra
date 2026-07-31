import { apiClient } from "@/lib/apiClient"

export const toolService = {
  list: (limit = 50, offset = 0, q = "") => {
    let endpoint = `/api/tools?limit=${limit}&offset=${offset}`
    if (q) {
      endpoint += `&q=${encodeURIComponent(q)}`
    }
    return apiClient.get(endpoint)
  },
  
  save: (toolData) => {
    return apiClient.post("/api/tools", toolData)
  },
  
  delete: (toolId) => {
    return apiClient.delete(`/api/tools/${toolId}`)
  },
  
  execute: (toolId, parameters) => {
    return apiClient.post(`/api/tools/${toolId}/execute`, { parameters })
  }
}
