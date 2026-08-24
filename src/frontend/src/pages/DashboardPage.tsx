import { CarrierDelayRateChart } from '@/components/dashboard/CarrierDelayRateChart'
import { ChartCard } from '@/components/dashboard/ChartCard'
import { DeliveryPerformanceChart } from '@/components/dashboard/DeliveryPerformanceChart'
import { KpiRow } from '@/components/dashboard/KpiRow'
import { OrderVolumeChart } from '@/components/dashboard/OrderVolumeChart'
import { AppHeader } from '@/components/layout/AppHeader'
import { AppSidebar, type AppPage } from '@/components/layout/AppSidebar'
import { useChart } from '@/hooks/useChart'
import { useKpis } from '@/hooks/useKpis'
import { CHART_ROUTES } from '@/lib/api'

type DashboardPageProps = {
  onNavigate: (page: AppPage) => void
}

/**
 * S1.5 - the dashboard of `docs/design/Main.dc.html`: five KPI cards and three charts.
 *
 * This component composes and nothing else. It owns no state of its own, holds no formula,
 * and does no arithmetic - every number on the page was computed by `calculator/` and is
 * printed exactly as it arrived (architecture Decision 1).
 *
 * Four independent requests rather than one composed endpoint: that is decision D9, and it
 * is why the front-end - not the backend - decides that order volume is a line and carrier
 * delay is a bar. Each section fails on its own; a dead chart route never blanks the KPIs.
 *
 * Every hook sits above every return (react rule 12), so no conditional path can change the
 * hook order.
 */
export default function DashboardPage({ onNavigate }: DashboardPageProps) {
  const kpis = useKpis()
  const orderVolume = useChart(CHART_ROUTES.orderVolume)
  const deliveryPerformance = useChart(CHART_ROUTES.deliveryPerformance)
  const carrierDelayRate = useChart(CHART_ROUTES.carrierDelayRate)

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <AppSidebar current="dashboard" onNavigate={onNavigate} />

      <div className="flex min-w-0 grow flex-col">
        <AppHeader />

        <main className="flex grow flex-col gap-4 p-6" data-testid="dashboard">
          <KpiRow state={kpis} />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <ChartCard
              testId="order-volume"
              title="Order volume over time"
              subtitle="Orders per month across the full dataset"
              badgeLabel="Line"
              state={orderVolume}
              className="lg:col-span-2"
            >
              {(rows) => <OrderVolumeChart rows={rows} />}
            </ChartCard>

            <ChartCard
              testId="delivery-performance"
              title="Delivery performance"
              subtitle="On time vs late, per month"
              badgeLabel="Stacked"
              state={deliveryPerformance}
            >
              {(rows) => <DeliveryPerformanceChart rows={rows} />}
            </ChartCard>
          </div>

          <ChartCard
            testId="carrier-delay-rate"
            title="Carrier breakdown"
            subtitle="Share arriving late, per carrier"
            badgeLabel="Bar"
            state={carrierDelayRate}
          >
            {(rows) => <CarrierDelayRateChart rows={rows} />}
          </ChartCard>
        </main>
      </div>
    </div>
  )
}
