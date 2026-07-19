"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useGetLogsQuery } from "@/lib/store";
import type { LogEntry, LogFilters } from "@/lib/types/logs";
import { AlertTriangle, RefreshCw } from "lucide-react";

const pagination = { limit: 100, offset: 0, sort_by: "timestamp" as const, order: "desc" as const };

function metadata(log: LogEntry, keys: string[]): string | undefined {
	for (const key of keys) {
		const value = log.metadata?.[key]?.trim();
		if (value && value.length <= 80) return value;
	}
	return undefined;
}

/** Shows only aggregate entitlement outcomes; claims, groups, and identities never render. */
export function IdentityEntitlementSummary({ filters }: { filters: LogFilters }) {
	const { data, isLoading, isFetching, isError, refetch } = useGetLogsQuery({ filters, pagination });
	const logs = data?.logs ?? [];
	let observed = 0;
	let allowed = 0;
	let denied = 0;
	let stale = 0;
	const capabilities = new Set<string>();
	const reasons = new Set<string>();
	for (const log of logs) {
		const outcome = metadata(log, ["identity.entitlement.allowed", "identity_entitlement_allowed"]);
		if (!outcome) continue;
		observed += 1;
		if (outcome === "true" || outcome === "allowed") allowed += 1;
		else if (outcome === "false" || outcome === "denied") denied += 1;
		const capability = metadata(log, ["identity.entitlement.capability", "identity_entitlement_capability"]);
		if (capability) capabilities.add(capability);
		const reason = metadata(log, ["identity.entitlement.reason", "identity_entitlement_reason"]);
		if (reason === "stale_snapshot" || reason === "epoch_mismatch" || reason === "revoked") stale += 1;
		if (reason) reasons.add(reason);
	}

	if (isError) return <Alert variant="warning" data-testid="dashboard-identity-summary-error"><AlertTriangle /><AlertTitle>Identity decisions unavailable</AlertTitle><AlertDescription>Entitlement outcomes could not be loaded for this authenticated scope. Claims and group details remain hidden.</AlertDescription></Alert>;

	return <section className="rounded-sm border p-3" data-testid="dashboard-identity-entitlement-summary" aria-label="Identity entitlement decisions">
		<div className="mb-2 flex items-center justify-between gap-2"><div><h2 className="text-sm font-semibold">Identity and entitlement decisions</h2><p className="text-muted-foreground text-xs">Aggregate authorization outcomes for the selected team or user scope. Raw claims and groups are never displayed.</p></div><Button variant="ghost" size="sm" onClick={() => void refetch()} disabled={isFetching} data-testid="dashboard-identity-refresh"><RefreshCw className={isFetching ? "animate-spin" : ""} />Refresh</Button></div>
		{isLoading ? <div className="text-muted-foreground py-3 text-center text-xs">Loading identity decisions…</div> : <>
			<div className="grid gap-2 sm:grid-cols-4"><div className="rounded border p-2"><div className="text-muted-foreground text-xs">Decisions observed</div><div className="text-lg font-semibold" data-testid="dashboard-identity-observed">{observed}</div></div><div className="rounded border p-2"><div className="text-muted-foreground text-xs">Allowed</div><div className="text-lg font-semibold">{allowed}</div></div><div className="rounded border p-2"><div className="text-muted-foreground text-xs">Denied</div><div className="text-lg font-semibold">{denied}</div></div><div className="rounded border p-2"><div className="text-muted-foreground text-xs">Stale/revoked</div><div className="text-lg font-semibold">{stale || "—"}</div></div></div>
			{(capabilities.size > 0 || reasons.size > 0) && <div className="mt-2 flex flex-wrap gap-1">{[...capabilities].slice(0, 8).map((value) => <Badge key={`cap-${value}`} variant="outline">capability: {value}</Badge>)}{[...reasons].slice(0, 8).map((value) => <Badge key={`reason-${value}`} variant={value === "revoked" || value === "stale_snapshot" ? "warning" : "outline"}>reason: {value}</Badge>)}</div>}
			{logs.length > 0 && observed < logs.length && <div className="mt-2 text-xs text-amber-700" data-testid="dashboard-identity-incomplete">Identity decision metadata is incomplete for {logs.length - observed} of {logs.length} requests; unobserved claims are not inferred.</div>}
		</>}
	</section>;
}
