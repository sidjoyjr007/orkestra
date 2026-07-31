import { configureStore } from "@reduxjs/toolkit"
import toolsReducer from "./slices/toolsSlice"
import configReducer from "./slices/configSlice"
import authReducer from "./slices/authSlice"
import agentsReducer from "./slices/agentsSlice"
import sessionsReducer from "./slices/sessionsSlice"

export const store = configureStore({
  reducer: {
    tools: toolsReducer,
    config: configReducer,
    auth: authReducer,
    agents: agentsReducer,
    sessions: sessionsReducer
  }
})
