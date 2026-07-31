import { createSlice } from "@reduxjs/toolkit"

const configSlice = createSlice({
  name: "config",
  initialState: {
    agent: {
      id: "foundry-bot",
      name: "FoundryBot",
      system_prompt: "You are FoundryBot, a helpful AI developer assistant. Keep answers concise."
    },
    llm: {
      provider: "gemini",
      config: {
        model: "gemini-2.5-flash",
        api_key: ""
      }
    },
    memory: {
      provider: "in-memory"
    },
    tools: [],
    guardrails: []
  },
  reducers: {
    setConfig: (state, action) => {
      return action.payload
    }
  }
})

export const { setConfig } = configSlice.actions
export default configSlice.reducer
