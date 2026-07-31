import { createSlice } from "@reduxjs/toolkit"

const sessionsSlice = createSlice({
  name: "sessions",
  initialState: {
    items: [],
    activeSessionId: ""
  },
  reducers: {
    createSession: (state, action) => {
      const { agentId, agentName } = action.payload
      const newSessionId = `session-${agentId}-${Date.now()}`
      const newSession = {
        id: newSessionId,
        agentId: agentId,
        agentName: agentName,
        messages: [
          { role: "assistant", content: `Hello! Session initialized for '${agentName}'. Send a prompt to run.` }
        ]
      }
      state.items.unshift(newSession)
      state.activeSessionId = newSessionId
    },
    setActiveSessionId: (state, action) => {
      state.activeSessionId = action.payload
    },
    sendMessage: (state, action) => {
      const { sessionId, userMessage, assistantReply } = action.payload
      state.items = state.items.map(sess => {
        if (sess.id === sessionId) {
          return {
            ...sess,
            messages: [
              ...sess.messages.filter(m => m.content !== userMessage || m.role !== "user"),
              { role: "user", content: userMessage },
              { role: "assistant", content: assistantReply }
            ]
          }
        }
        return sess
      })
    }
  }
})

export const { createSession, setActiveSessionId, sendMessage } = sessionsSlice.actions
export default sessionsSlice.reducer
