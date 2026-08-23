import DashboardPage from '@/pages/DashboardPage'

/**
 * The application shell.
 *
 * Slice 1 has exactly one page, so this is a single render and no router: adding one would
 * be machinery for a navigation that does not exist yet. Slice 2's "Ask AI" is the point at
 * which a second route earns its keep.
 */
export default function App() {
  return <DashboardPage />
}
