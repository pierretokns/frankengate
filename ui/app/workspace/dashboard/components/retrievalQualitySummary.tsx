"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useGetLogsQuery } from "@/lib/store";
import type { LogEntry, LogFilters } from "@/lib/types/logs";
import { AlertTriangle, RefreshCw } from "lucide-react";

const pagination = { limit: 100, offset: 0, sort_by: "timestamp" as const, order: "desc" as const };
const signalKeys = ["retrieval_score", "retrieval_quality", "retrieval_relevance", "rag_score", "eval_score", "groundedness"];

function numberSignal(log: LogEntry): number | undefined {

	const metadata = log.metadata ?? {};
	for (const key of signalKeys) {
		const value = metadata[key];
		const parsed = typeof value === "number" ? value : typeof value === "string" ? Number(value) : NaN;
		if (Number.isFinite(parsed) && parsed >= 0 && parsed <= 1) return parsed;
	}
	const rerank = log.rerank_output?.map((item) => item.relevance_score).filter((score) => Number.isFinite(score));
	if (rerank?.length) return rerank.reduce((sum, score) => sum + score, 0) / rerank.length;
	return undefined;
}

export function RetrievalQualitySummary({ filters }: { filters: LogFilters }) {
	const { data, isLoading, isFetching, isError, refetch } = useGetLogsQuery({ filters, pagination });
	const logs = data?.logs ?? [];
	const signals = logs.map(numberSignal).filter((value): value is number => value !== undefined);
	const average = signals.length ? signals.reduce((sum, value) => sum + value, 0) / signals.length : undefined;
	const redacted = logs.filter((log) => Boolean(log.redaction_mapping) || log.metadata?.redacted === "true").length;

	if (isError) {
		return <Alert variant="warning" data-testid="dashboard-retrieval-quality-error"><AlertTriangle /><AlertTitle>Retrieval quality unavailable</AlertTitle><AlertDescription>Quality signals could not be loaded for this authenticated scope.</AlertDescription></Alert>;
	}

	return (
		<section className="rounded-sm border p-3" data-testid="dashboard-retrieval-quality" aria-label="Retrieval quality summary">
			<div className="mb-2 flex items-center justify-between gap-2">
				<div><h2 className="text-sm font-semibold">Retrieval quality</h2><p className="text-muted-foreground text-xs">Derived only from governed, redacted logs in the selected team or user scope.</p></div>
				<Button variant="ghost" size="sm" onClick={() => void refetch()} disabled={isFetching} data-testid="dashboard-retrieval-quality-refresh"><RefreshCw className={isFetching ? "animate-spin" : ""} />Refresh</Button>
			</div>
			{isLoading ? <div className="text-muted-foreground py-3 text-center text-xs">Loading quality signals…</div> : (
				<div className="grid gap-2 sm:grid-cols-3">
					<div className="rounded border p-2"><div className="text-muted-foreground text-xs">Scored requests</div><div className="text-lg font-semibold" data-testid="dashboard-retrieval-scored">{signals.length}</div></div>
					<div className="rounded border p-2"><div className="text-muted-foreground text-xs">Mean relevance</div><div className="text-lg font-semibold" data-testid="dashboard-retrieval-average">{average === undefined ? "—" : average.toFixed(2)}</div></div>
					<div className="rounded border p-2"><div className="text-muted-foreground text-xs">Redacted evidence</div><div className="text-lg font-semibold"><Badge variant="outline">{redacted} / {logs.length}</Badge></div></div>
				</div>
			)}
			{!isLoading && logs.length > 0 && signals.length === 0 && <div className="mt-2 text-xs text-amber-700" data-testid="dashboard-retrieval-incomplete">Quality signals are incomplete for this window; no scored retrieval evidence was emitted.</div>}
		</section>
	);
}
