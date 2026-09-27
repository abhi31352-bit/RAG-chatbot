import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { MessageCircle, FolderOpen, Home } from 'lucide-react'

/**
 * Primary navigation.
 *
 * Rendered by `AppRoutes` above the routed outlet rather than by each page, so
 * it stays put across navigation and has one definition. Placing it inside the
 * router means `useLocation` is safe to call.
 */
const NAV_ITEMS = [
  { path: '/', label: 'Home', icon: Home },
  { path: '/chat', label: 'Chat', icon: MessageCircle },
  { path: '/admin', label: 'Documents', icon: FolderOpen },
]

export const Header: React.FC = () => {
  const location = useLocation()

  return (
    <nav aria-label="Primary" className="border-b bg-white">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        {/* The wordmark is the way home, not a shortcut to the chat: on the
            landing page the two are different, and a logo that navigates
            somewhere other than where it looks like it goes is a small trap. */}
        <Link to="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
            <MessageCircle className="h-5 w-5 text-white" aria-hidden="true" />
          </div>
          <span className="font-semibold text-gray-900">RAG Chatbot</span>
        </Link>

        <div className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path
            return (
              <Link
                key={item.path}
                to={item.path}
                aria-current={isActive ? 'page' : undefined}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Link>
            )
          })}
        </div>
      </div>
    </nav>
  )
}
