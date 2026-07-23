import { createFileRoute } from "@tanstack/react-router";
import MyHistoryPage from "./page";

export const Route = createFileRoute("/workspace/my-history")({
	component: MyHistoryPage,
});