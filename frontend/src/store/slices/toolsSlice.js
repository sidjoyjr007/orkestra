import { createSlice } from "@reduxjs/toolkit"

const toolsSlice = createSlice({
  name: "tools",
  initialState: {
    items: [],
    searchQuery: "",
  },
  reducers: {
    setTools: (state, action) => {
      state.items = action.payload
    },
    saveTool: (state, action) => {
      const idx = state.items.findIndex(t => t.id === action.payload.id)
      if (idx !== -1) {
        state.items[idx] = action.payload
      } else {
        state.items.push(action.payload)
      }
    },
    removeTool: (state, action) => {
      state.items = state.items.filter(t => t.id !== action.payload)
    },
    setSearchQuery: (state, action) => {
      state.searchQuery = action.payload
    }
  }
})

export const { setTools, saveTool, removeTool, setSearchQuery } = toolsSlice.actions
export default toolsSlice.reducer
