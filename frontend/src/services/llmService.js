import { apiClient } from "@/lib/apiClient"

export const llmService = {
  list: () => {
    return apiClient.get("/api/llms")
  },
  
  create: (llmData) => {
    return apiClient.post("/api/llms", llmData)
  },
  
  update: (llmId, llmData) => {
    return apiClient.put(`/api/llms/${llmId}`, llmData)
  },
  
  delete: (llmId) => {
    return apiClient.delete(`/api/llms/${llmId}`)
  },
  
  test: (llmId, prompt) => {
    return apiClient.post(`/api/llms/${llmId}/test`, { prompt })
  }
}
