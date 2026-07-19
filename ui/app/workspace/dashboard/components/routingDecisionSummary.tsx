"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useGetLogsQuery } from "@/lib/store";
import type { LogEntry, LogFilters } from "@/lib/types/logs";
import { AlertTriangle, RefreshCw } from "lucide-react";

const pagination = { limit: 50, offset: 0, sort_by: "timestamp" as const, order: "desc" as const };
const metadataKeys = {
	region: ["destination_region", "routing_region", "bifrost.routing.selected_destination_region", "bifrost.routing.required_destination_region"],
	circuitState: ["circuit_state", "bifrost.circuit.state"],
	circuitReason: ["circuit_reason", "bifrost.circuit.reason"],
	circuitAllowed: ["circuit_allowed", "bifrost.circuit.allowed"],
} as const;

function firstMetadata(log: LogEntry, keys: readonly string[]): string | undefined {
	for (const key of keys) {
		const value = log.metadata?.[key]?.trim();
		if (value && value.length <= 80) return value;
	}
	return undefined;
}

function routingValues(log: LogEntry) {
	const fallback = Number(log.fallback_index || 0);
	return {
		region: firstMetadata(log, metadataKeys.region),
		circuitState: firstMetadata(log, metadataKeys.circuitState),
		circuitReason: firstMetadata(log, metadataKeys.circuitReason),
		circuitAllowed: firstMetadata(log, metadataKeys.circuitAllowed),
		fallback: Number.isFinite(fallback) && fallback > 0 ? fallback : 0,
	};
}

export function RoutingDecisionSummary({ filters }: { filters: LogFilters }) {
	const { data, isLoading, isFetching, isError, refetch } = useGetLogsQuery({ filters, pagination });
	const logs = data?.logs ?? [];

	if (isError) {
		return (
			<Alert variant="warning" data-testid="dashboard-routing-summary-error">
				<AlertTriangle />
				<AlertTitle>Routing evidence unavailable</AlertTitle>
				<AlertDescription>Routing decisions could not be loaded for this authenticated scope.</AlertDescription>
			</Alert>
		);
	}

	const rows = logs.map(routingValues);
	const fallbackCount = rows.filter((row) => row.fallback > 0).length;
	const circuitDenied = rows.filter((row) => row.circuitAllowed === "false" || row.circuitState === "open").length;
	const regions = [...new Set(rows.map((row) => row.region).filter(Boolean))] as string[];
	const states = [...new Set(rows.map((row) => row.circuitState).filter(Boolean))] as string[];

	return (
		<section className="rounded-sm border p-3" data-testid="dashboard-routing-decision-summary" aria-label="Routing decisions">
			<div className="mb-2 flex items-center justify-between gap-2">
				<div>
					<h2 className="text-sm font-semibold">Routing decisions</h2>
					<p className="text-muted-foreground text-xs">Bounded provider, fallback, circuit, and region signals for this team/user scope.</p>
				</div>
				<Button variant="ghost" size="sm" onClick={() => void refetch()} disabled={isFetching} data-testid="dashboard-routing-refresh">
					<RefreshCw className={isFetching ? "animate-spin" : ""} />
					Refresh
				</Button>
			</div>
			{isLoading ? (
				<div className="text-muted-foreground py-4 text-center text-xs">Loading routing evidence…</div>
			) : logs.length === 0 ? (
				<div className="text-muted-foreground py-4 text-center text-xs">No routing decisions in this scope and time window.</div>
			) : (
				<div className="grid gap-2 sm:grid-cols-4" data-testid="dashboard-routing-metrics">
					<div className="rounded-sm bg-muted/40 p-2"><div className="text-muted-foreground text-[11px]">Requests sampled</div><div className="text-lg font-semibold">{logs.length}</div></div>
					<div className="rounded-sm bg-muted/40 p-2"><div className="text-muted-foreground text-[11px]">Fallback attempts</div><div className="text-lg font-semibold">{fallbackCount}</div></div>
					<div className="rounded-sm bg-muted/40 p-2"><div className="text-muted-foreground text-[11px]">Circuit denied/open</div><div className="text-lg font-semibold">{circuitDenied}</div></div>
					<div className="rounded-sm bg-muted/40 p-2"><div className="text-muted-foreground text-[11px]">Regions observed</div><div className="text-lg font-semibold">{regions.length || "—"}</div></div>
				</div>
			)}
			{(regions.length > 0 || states.length > 0) && (
				<div className="mt-2 flex flex-wrap gap-1" data-testid="dashboard-routing-badges">
					{regions.slice(0, 8).map((region) => <Badge key={`region-${region}`} variant="outline">region: {region}</Badge>)}
					{states.slice(0, 8).map((state) => <Badge key={`state-${state}`} variant={state === "open" ? "warning" : "outline"}>circuit: {state}</Badge>)}
				</div>
			)}
		</section>
	);
}
