import { useState } from 'react'

import type { AppPage } from '@/components/layout/AppSidebar'
import ChatPage from '@/pages/ChatPage'
import DashboardPage from '@/pages/DashboardPage'

/**
 * The application shell.
 *
 * Slice 2 adds the second screen, and it is a `useState` rather than a router. Two pages,
 * no deep links and no browser back were asked for, so `react-router-dom` would be a
 * runtime dependency and a provider bought for one boolean. That is the trade-off: the
 * chat has no URL of its own, and a reload always lands on the dashboard.
 *
 * Both pages get `onNavigate`, so the sidebar is the only thing that knows how to switch
 * and neither page knows the other exists.
 */
export default function App() {
  const [page, setPage] = useState<AppPage>('dashboard')

  return page === 'chat' ? (
    <ChatPage onNavigate={setPage} />
  ) : (
    <DashboardPage onNavigate={setPage} />
  )
}
