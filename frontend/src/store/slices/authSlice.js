import { createSlice, createAsyncThunk } from "@reduxjs/toolkit"
import { apiClient } from "@/lib/apiClient"

export const fetchCurrentUser = createAsyncThunk(
  "auth/fetchCurrentUser",
  async (_, { rejectWithValue }) => {
    try {
      return await apiClient.get("/api/auth/me")
    } catch (err) {
      return rejectWithValue(err.message)
    }
  }
)

export const logoutUser = createAsyncThunk(
  "auth/logoutUser",
  async (_, { rejectWithValue }) => {
    try {
      await apiClient.post("/api/auth/logout")
      return null
    } catch (err) {
      return rejectWithValue(err.message)
    }
  }
)

const authSlice = createSlice({
  name: "auth",
  initialState: {
    currentUser: null,
    isAuthenticated: false,
    checkingAuth: true,
    error: null
  },
  reducers: {
    setCurrentUser: (state, action) => {
      state.currentUser = action.payload
      state.isAuthenticated = !!action.payload
      state.checkingAuth = false
    },
    clearAuth: (state) => {
      state.currentUser = null
      state.isAuthenticated = false
      state.checkingAuth = false
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchCurrentUser.pending, (state) => {
        state.error = null
      })
      .addCase(fetchCurrentUser.fulfilled, (state, action) => {
        state.currentUser = action.payload
        state.isAuthenticated = true
        state.checkingAuth = false
      })
      .addCase(fetchCurrentUser.rejected, (state, action) => {
        state.currentUser = null
        state.isAuthenticated = false
        state.checkingAuth = false
      })
      .addCase(logoutUser.fulfilled, (state) => {
        state.currentUser = null
        state.isAuthenticated = false
      })
  }
})

export const { setCurrentUser, clearAuth } = authSlice.actions
export default authSlice.reducer
