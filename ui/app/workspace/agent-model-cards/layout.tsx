import { createFileRoute } from "@tanstack/react-router";
import AgentModelCardsPage from "./page";

export const Route = createFileRoute("/workspace/agent-model-cards")({
	component: AgentModelCardsPage,
});
