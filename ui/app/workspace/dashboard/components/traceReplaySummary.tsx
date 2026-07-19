"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useGetLogsQuery } from "@/lib/store";
import type { LogEntry, LogFilters } from "@/lib/types/logs";
import { AlertTriangle, ExternalLink, RefreshCw } from "lucide-react";

const recentPagination = { limit: 6, offset: 0, sort_by: "timestamp" as const, order: "desc" as const };

function traceId(log: LogEntry): string | undefined {
	const metadata = log.metadata ?? {};
	return metadata.trace_id ?? metadata.traceId ?? metadata["otel.trace_id"];
}

function replayHref(log: LogEntry): string {
	const requestId = log.parent_request_id || log.id;
	return `/workspace/logs?parent_request_id=${encodeURIComponent(requestId)}`;
}

function retrievalQuality(log: LogEntry): { precision: number; recall: number } | undefined {
	const metadata = log.metadata ?? {};
	const precision = Number(metadata["frankengate.retrieval.precision"]);
	const recall = Number(metadata["frankengate.retrieval.recall"]);
	if (!Number.isFinite(precision) || !Number.isFinite(recall) || precision < 0 || precision > 1 || recall < 0 || recall > 1) return undefined;
	return { precision, recall };
}

export function TraceReplaySummary({ filters }: { filters: LogFilters }) {
	const { data, isLoading, isFetching, isError, refetch } = useGetLogsQuery({ filters, pagination: recentPagination });
	const logs = data?.logs ?? [];

	if (isError) {
		return (
			<Alert variant="warning" data-testid="dashboard-trace-summary-error">
				<AlertTriangle />
				<AlertTitle>Trace evidence unavailable</AlertTitle>
				<AlertDescription>Governed logs could not be loaded for this scope. No trace or replay links are shown.</AlertDescription>
			</Alert>
		);
	}

	return (
		<section className="rounded-sm border p-3" data-testid="dashboard-trace-replay-summary" aria-label="Recent governed traces">
			<div className="mb-2 flex items-center justify-between gap-2">
				<div>
					<h2 className="text-sm font-semibold">Recent governed traces</h2>
					<p className="text-muted-foreground text-xs">Tenant-scoped evidence from the authenticated logs endpoint. Content remains redacted.</p>
				</div>
				<Button variant="ghost" size="sm" onClick={() => void refetch()} disabled={isFetching} data-testid="dashboard-trace-refresh">
					<RefreshCw className={isFetching ? "animate-spin" : ""} />
					Refresh
				</Button>
			</div>
			{isLoading ? (
				<div className="text-muted-foreground py-4 text-center text-xs">Loading governed traces…</div>
			) : logs.length === 0 ? (
				<div className="text-muted-foreground py-4 text-center text-xs">No governed traces in this scope and time window.</div>
			) : (
				<div className="divide-y">
					{logs.map((log) => {
						const trace = traceId(log);
						const redacted = Boolean(log.redaction_mapping) || Boolean(log.metadata?.redacted === "true");
						const quality = retrievalQuality(log);
						return (
							<div key={log.id} className="flex items-center justify-between gap-3 py-2 text-xs" data-testid="dashboard-trace-row">
								<div className="min-w-0">
									<div className="flex items-center gap-2">
										<span className="font-medium">{log.model || "Unknown model"}</span>
										<Badge variant={log.status === "success" ? "success" : "warning"}>{log.status}</Badge>
										{redacted && <Badge variant="outline">redacted</Badge>}
										{quality && <Badge variant="outline">retrieval P/R {(quality.precision * 100).toFixed(0)}/{(quality.recall * 100).toFixed(0)}</Badge>}
									</div>
									<div className="text-muted-foreground truncate">
										{trace ? `trace ${trace}` : `request ${log.id}`} · {log.team_name || "tenant scope"}
									</div>
								</div>
								<a href={replayHref(log)} className="text-primary inline-flex shrink-0 items-center gap-1 hover:underline" data-testid="dashboard-trace-replay-link">
									Replay context <ExternalLink className="size-3" />
								</a>
							</div>
						);
					})}
				</div>
			)}
		</section>
	);
}
