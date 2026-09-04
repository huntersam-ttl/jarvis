import { PageHeader, PlaceholderModule } from "@/components/ui";

export default function ProjectsPage() {
  return (
    <>
      <PageHeader
        title="Projects"
        subtitle="Project tracking inside Jarvis"
      />
      <PlaceholderModule
        title="Projects Module"
        phase="1+"
        icon="▦"
        bullets={[
          "Track personal projects, notes and status",
          "Link tasks and chat history to projects",
          "Designed after the task engine lands",
        ]}
      />
    </>
  );
}
