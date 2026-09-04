import { PageHeader, PlaceholderModule } from "@/components/ui";

export default function MemoryPage() {
  return (
    <>
      <PageHeader
        title="Memory"
        subtitle="Long-term memory for Jarvis"
      />
      <PlaceholderModule
        title="Memory Module"
        phase="1+"
        icon="◌"
        bullets={[
          "Persist preferences, facts and past conversations",
          "Local-first storage; no external services required",
          "Plugs into the chat pipeline once designed",
        ]}
      />
    </>
  );
}
