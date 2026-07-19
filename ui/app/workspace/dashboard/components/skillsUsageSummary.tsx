"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useGetLogsQuery } from "@/lib/store";
import type { LogEntry, LogFilters } from "@/lib/types/logs";
import { AlertTriangle, RefreshCw } from "lucide-react";

const pagination = { limit: 100, offset: 0, sort_by: "timestamp" as const, order: "desc" as const };

function values(metadata: Record<string, string> | undefined, keys: string[]): string[] {
	for (const key of keys) {
		const value = metadata?.[key];
		if (!value) continue;
		const parsed = value.split(",").map((item) => item.trim()).filter(Boolean);
		if (parsed.length) return parsed.slice(0, 20);
	}
	return [];
}

function skillNames(log: LogEntry): string[] {
	return values(log.metadata, ["skill", "skill_name", "skill_names", "frankengate.skill", "frankengate.skills"]);
}

function toolNames(log: LogEntry): string[] {
	const metadataTools = values(log.metadata, ["tool", "tool_name", "tool_names", "frankengate.tool", "frankengate.tools"]);
	const responseTools = (log.tool_calls ?? []).map((call) => call.function?.name).filter((name): name is string => Boolean(name));
	return [...new Set([...metadataTools, ...responseTools])].slice(0, 20);
}

function increment(target: Map<string, number>, names: string[]) {
	for (const name of names) target.set(name, (target.get(name) ?? 0) + 1);
}

function topEntries(target: Map<string, number>) {
	return [...target.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 5);
}

export function SkillsUsageSummary({ filters }: { filters: LogFilters }) {
	const { data, isLoading, isFetching, isError, refetch } = useGetLogsQuery({ filters, pagination });
	const logs = data?.logs ?? [];
	const skills = new Map<string, number>();
	const tools = new Map<string, number>();
	const sessions = new Set<string>();
	let attributed = 0;
	let redacted = 0;
	for (const log of logs) {
		const currentSkills = skillNames(log);
		const currentTools = toolNames(log);
		increment(skills, currentSkills);
		increment(tools, currentTools);
		if (currentSkills.length || currentTools.length) attributed += 1;
		if (log.redaction_mapping || log.metadata?.redacted === "true") redacted += 1;
		if (log.parent_request_id || log.id) sessions.add(log.parent_request_id || log.id);
	}
	const incomplete = logs.length > 0 && attributed < logs.length;

	if (isError) {
		return <Alert variant="warning" data-testid="dashboard-skills-usage-error"><AlertTriangle /><AlertTitle>Skill usage unavailable</AlertTitle><AlertDescription>Usage attribution could not be loaded for this authenticated scope. No inferred tool or skill data is shown.</AlertDescription></Alert>;
	}

	return (
		<section className="rounded-sm border p-3" data-testid="dashboard-skills-usage" aria-label="Skills and tool usage summary">
			<div className="mb-2 flex items-center justify-between gap-2">
				<div><h2 className="text-sm font-semibold">Skills, tools, and sessions</h2><p className="text-muted-foreground text-xs">Derived from governed logs in the selected team or user scope; no payloads are displayed.</p></div>
				<Button variant="ghost" size="sm" onClick={() => void refetch()} disabled={isFetching} data-testid="dashboard-skills-usage-refresh"><RefreshCw className={isFetching ? "animate-spin" : ""} />Refresh</Button>
			</div>
			{isLoading ? <div className="text-muted-foreground py-3 text-center text-xs">Loading usage attribution…</div> : (
				<>
					<div className="grid gap-2 sm:grid-cols-4">
						<div className="rounded border p-2"><div className="text-muted-foreground text-xs">Requests</div><div className="text-lg font-semibold" data-testid="dashboard-skills-requests">{logs.length}</div></div>
						<div className="rounded border p-2"><div className="text-muted-foreground text-xs">Sessions</div><div className="text-lg font-semibold" data-testid="dashboard-skills-sessions">{sessions.size}</div></div>
						<div className="rounded border p-2"><div className="text-muted-foreground text-xs">Skills observed</div><div className="text-lg font-semibold" data-testid="dashboard-skills-count">{skills.size}</div></div>
						<div className="rounded border p-2"><div className="text-muted-foreground text-xs">Tools observed</div><div className="text-lg font-semibold" data-testid="dashboard-tools-count">{tools.size}</div></div>
					</div>
					<div className="mt-3 grid gap-3 sm:grid-cols-2">
						<div><div className="mb-1 text-xs font-medium">Top skills</div>{topEntries(skills).length ? <div className="flex flex-wrap gap-1">{topEntries(skills).map(([name, count]) => <Badge key={name} variant="outline">{name} · {count}</Badge>)}</div> : <span className="text-muted-foreground text-xs">No skill attribution emitted.</span>}</div>
						<div><div className="mb-1 text-xs font-medium">Top tools</div>{topEntries(tools).length ? <div className="flex flex-wrap gap-1">{topEntries(tools).map(([name, count]) => <Badge key={name} variant="outline">{name} · {count}</Badge>)}</div> : <span className="text-muted-foreground text-xs">No tool attribution emitted.</span>}</div>
					</div>
					{incomplete && <div className="mt-2 text-xs text-amber-700" data-testid="dashboard-skills-usage-incomplete">Attribution is incomplete for {logs.length - attributed} of {logs.length} requests; summaries exclude data that was not emitted or was redacted.</div>}
					{redacted > 0 && <div className="mt-1 text-xs text-muted-foreground" data-testid="dashboard-skills-usage-redacted">{redacted} request{redacted === 1 ? "" : "s"} contain redacted evidence; payloads remain hidden.</div>}
				</>
			)}
		</section>
	);
}
