import { createSlice, createAsyncThunk } from "@reduxjs/toolkit"
import { agentService } from "@/services/agentService"

export const fetchAgents = createAsyncThunk(
  "agents/fetchAgents",
  async (_, { rejectWithValue }) => {
    try {
      const data = await agentService.list()
      return data.items.map(a => ({
        ...a,
        toolsCount: a.selectedTools?.length || 0,
        mcpCount: a.selectedMcps?.length || 0,
        guardrailEnabled: a.selectedGuardrails?.length > 0,
      }))
    } catch (err) {
      return rejectWithValue(err.message)
    }
  }
)

export const deleteAgent = createAsyncThunk(
  "agents/deleteAgent",
  async (agentId, { rejectWithValue }) => {
    try {
      await agentService.delete(agentId)
      return agentId
    } catch (err) {
      return rejectWithValue(err.message)
    }
  }
)

const agentsSlice = createSlice({
  name: "agents",
  initialState: {
    items: [],
    loading: false,
    error: null
  },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchAgents.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchAgents.fulfilled, (state, action) => {
        state.items = action.payload
        state.loading = false
      })
      .addCase(fetchAgents.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload
      })
      .addCase(deleteAgent.fulfilled, (state, action) => {
        state.items = state.items.filter(a => a.id !== action.payload)
      })
  }
})

export default agentsSlice.reducer
