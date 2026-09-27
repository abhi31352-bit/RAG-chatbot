import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Header } from './components/Common/Header'
import { ChatPage } from './pages/ChatPage'
import { AdminPage } from './pages/AdminPage'
import { LandingPage } from './pages/LandingPage'

/**
 * The routed application, minus the router.
 *
 * Split out from `App` so tests can mount it inside a `MemoryRouter` and drive
 * a real history. A single `BrowserRouter` reads the live address bar, which
 * jsdom does not let a test move, so testing navigation through `App` itself
 * would only ever see one URL.
 *
 * The Header sits outside `Routes` so it survives navigation. Rendering it
 * per-page instead would duplicate it in three files and let the copies drift;
 * the plan's `LandingPage` snippet does exactly that, which would have put two
 * headers on `/` had `LandingPage` also been routed at `/`.
 */
export function AppRoutes(): React.JSX.Element {
  return (
    <div className="flex h-screen flex-col">
      <Header />
      <div className="min-h-0 flex-1">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  )
}

/**
 * `/` is the landing page rather than a redirect into the chat, so the app has
 * a front door that explains what it is. `/chat` remains a real route: a
 * refresh on it must not land the presenter somewhere else mid-demo.
 */
function App(): React.JSX.Element {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}

export { App }
export default App
