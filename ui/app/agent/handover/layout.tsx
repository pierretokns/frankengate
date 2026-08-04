import { ThemeProvider } from "@/components/themeProvider";
import { createFileRoute } from "@tanstack/react-router";
import AgentHandoverPage from "./page";

function RouteComponent() {
	return (
		<ThemeProvider attribute="class" defaultTheme="system" enableSystem>
			<AgentHandoverPage />
		</ThemeProvider>
	);
}

export const Route = createFileRoute("/agent/handover")({
	// This route is opened by the local agent after an authentication handoff;
	// it intentionally does not require a dashboard session.
	staticData: { publicRoute: true },
	component: RouteComponent,
});
