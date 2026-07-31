import { apiClient } from "@/lib/apiClient"

export const agentService = {
  list: (limit = 50, offset = 0, q = "") => {
    let endpoint = `/api/agents?limit=${limit}&offset=${offset}`
    if (q) {
      endpoint += `&q=${encodeURIComponent(q)}`
    }
    return apiClient.get(endpoint)
  },
  
  create: (agentData) => {
    return apiClient.post("/api/agents", agentData)
  },
  
  update: (agentId, agentData) => {
    return apiClient.put(`/api/agents/${agentId}`, agentData)
  },
  
  delete: (agentId) => {
    return apiClient.delete(`/api/agents/${agentId}`)
  }
}
