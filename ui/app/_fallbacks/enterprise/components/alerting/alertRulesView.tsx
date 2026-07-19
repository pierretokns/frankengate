"use client";

import { useState } from "react";
import {
	useCreateAlertRuleMutation,
	useDeleteAlertRuleMutation,
	useGetAlertHistoryQuery,
	useGetAlertRulesQuery,
	useUpdateAlertRuleMutation,
} from "@/lib/store/apis/alertingApi";
import type { AlertingScope } from "@/lib/store/apis/alertingApi";

/**
 * The fallback view intentionally exposes operational metadata only.  It does
 * not render channel configuration or delivery payloads, which are scoped by
 * the authenticated alerting API.
 */
export default function AlertRulesView() {
	const [viewScope, setViewScope] = useState<"global" | "team" | "user">("global");
	const [viewScopeId, setViewScopeId] = useState("");
	const scopeFilter: AlertingScope = { scope: viewScope, scope_id: viewScope === "global" ? undefined : viewScopeId.trim() || undefined };
	const scopedQuery = viewScope !== "global" && !viewScopeId.trim() ? undefined : scopeFilter;
	const { data, isLoading, error } = useGetAlertRulesQuery(scopedQuery);
	const { data: historyData } = useGetAlertHistoryQuery(scopedQuery);
	const [create] = useCreateAlertRuleMutation();
	const [update, { isLoading: isUpdating }] = useUpdateAlertRuleMutation();
	const [remove] = useDeleteAlertRuleMutation();
	const [name, setName] = useState("");
	const [event, setEvent] = useState("overdraft");
	const [scope, setScope] = useState<"global" | "team" | "user">("global");
	const [scopeId, setScopeId] = useState("");
	const [approvalRequired, setApprovalRequired] = useState(true);
	const rules = data?.rules ?? [];
	const history = historyData?.history ?? [];

	return (
		<section className="mx-auto w-full max-w-5xl space-y-6 p-8" data-testid="alert-rules-view">
			<div>
				<h1 className="text-2xl font-semibold">Alert rules</h1>
				<p className="text-sm text-muted-foreground">Manage delivery policies and inspect their latest operational status.</p>
			</div>
			<div className="flex flex-wrap items-center gap-2 rounded border p-3" data-testid="alert-scope-filter">
				<label className="text-sm" htmlFor="alert-view-scope">View</label>
				<select id="alert-view-scope" className="rounded border px-2 py-1" value={viewScope} onChange={(e) => setViewScope(e.target.value as "global" | "team" | "user")}>
					<option value="global">All users</option><option value="team">Team</option><option value="user">User</option>
				</select>
				{viewScope !== "global" && <input className="rounded border px-2 py-1" value={viewScopeId} onChange={(e) => setViewScopeId(e.target.value)} placeholder={`${viewScope} ID`} aria-label={`View ${viewScope} ID`} />}
				{viewScope !== "global" && !viewScopeId.trim() && <span className="text-xs text-muted-foreground">Enter an ID to load the scoped view.</span>}
			</div>
			<form
				className="flex flex-wrap gap-3 rounded border p-4"
				onSubmit={async (e) => {
					e.preventDefault();
					if (!name.trim()) return;
					if (scope !== "global" && !scopeId.trim()) return;
					await create({ name: name.trim(), event, channel_ids: [], enabled: true, scope, scope_id: scope === "global" ? undefined : scopeId.trim(), approval_required: event === "overdraft" && approvalRequired, approved: event !== "overdraft" || !approvalRequired }).unwrap();
					setName("");
					setScopeId("");
				}}
			>
				<input className="rounded border px-2 py-1" value={name} onChange={(e) => setName(e.target.value)} placeholder="Budget overdraft" aria-label="Rule name" />
				<select className="rounded border px-2 py-1" value={event} onChange={(e) => setEvent(e.target.value)} aria-label="Rule event">
					<option value="overdraft">Overdraft</option>
					<option value="budget_limit">Budget limit</option>
					<option value="delivery_failure">Delivery failure</option>
				</select>
				<select className="rounded border px-2 py-1" value={scope} onChange={(e) => setScope(e.target.value as "global" | "team" | "user")} aria-label="Rule scope">
					<option value="global">All users</option>
					<option value="team">Team</option>
					<option value="user">User</option>
				</select>
				{scope !== "global" && <input className="rounded border px-2 py-1" value={scopeId} onChange={(e) => setScopeId(e.target.value)} placeholder={`${scope} ID`} aria-label="Scope ID" />}
				{event === "overdraft" && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={approvalRequired} onChange={(e) => setApprovalRequired(e.target.checked)} /> Require approval</label>}
				<button className="rounded bg-primary px-3 py-1.5 text-primary-foreground" type="submit">Add rule</button>
			</form>
			{isLoading ? <p>Loading rules…</p> : error ? <p role="alert">Unable to load alert rules.</p> : (
				<ul className="divide-y rounded border">
					{rules.map((rule) => {
						const deliveries = history.filter((delivery) => delivery.rule_id === rule.id);
						const latest = deliveries[0];
						const failed = deliveries.filter((delivery) => delivery.status.toLowerCase() === "failed").length;
						return (
							<li className="flex flex-wrap items-center justify-between gap-3 p-3" key={rule.id}>
								<div className="min-w-0">
									<strong>{rule.name}</strong>
									<div className="text-xs text-muted-foreground">
										<span>{rule.event}</span> · <span>{rule.channel_ids.length} channel{rule.channel_ids.length === 1 ? "" : "s"}</span>
										<span className="ml-2">Scope: {rule.scope === "team" ? `team ${rule.scope_id ?? "(unknown)"}` : rule.scope === "user" ? `user ${rule.scope_id ?? "(unknown)"}` : "all users"}</span>
										{rule.event === "overdraft" && rule.approval_required && <span className={`ml-2 ${rule.approved ? "text-success" : "text-warning"}`}>{rule.approved ? "Approved" : "Approval required"}</span>}
										<span className="ml-2" data-testid={`alert-rule-status-${rule.id}`}>
											{latest ? `Latest: ${latest.status}${latest.created_at ? ` (${new Date(latest.created_at).toLocaleString()})` : ""}` : "No deliveries recorded"}
										</span>
										{failed > 0 && <span className="ml-2 text-destructive">{failed} failed</span>}
									</div>
								</div>
								<div className="flex items-center gap-2">
									<button
										type="button"
										className="rounded border px-2 py-1 text-xs"
										disabled={isUpdating}
										aria-label={`${rule.enabled ? "Disable" : "Enable"} ${rule.name}`}
										onClick={() => void update({ id: rule.id, data: { name: rule.name, event: rule.event, channel_ids: rule.channel_ids, enabled: !rule.enabled, scope: rule.scope ?? "global", scope_id: rule.scope_id, approval_required: rule.approval_required, approved: rule.approved } })}
									>
										{rule.enabled ? "Disable" : "Enable"}
									</button>
									<small>{rule.enabled ? "enabled" : "disabled"}</small>
									<button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => void remove(rule.id)}>Remove</button>
								</div>
							</li>
						);
					})}
					{rules.length === 0 && <li className="p-4 text-sm text-muted-foreground">No alert rules configured.</li>}
				</ul>
			)}
		</section>
	);
}
