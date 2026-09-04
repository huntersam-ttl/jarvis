import { PageHeader, PlaceholderModule } from "@/components/ui";

export default function TradingPage() {
  return (
    <>
      <PageHeader
        title="Trading"
        subtitle="Personal trading engine — planned module"
      />
      <PlaceholderModule
        title="Trading Engine"
        phase="2"
        icon="↗"
        bullets={[
          "Strategy research and paper trading first",
          "No broker or exchange APIs in Phase 1",
          "Risk limits and kill switch before any live activity",
          "Jarvis chat will be able to query trading status once installed",
        ]}
      />
    </>
  );
}
