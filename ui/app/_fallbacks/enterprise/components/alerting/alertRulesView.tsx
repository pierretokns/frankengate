"use client";

import { useState } from "react";
import {
	useCreateAlertRuleMutation,
	useDeleteAlertRuleMutation,
	useGetAlertHistoryQuery,
	useGetAlertRulesQuery,
	useUpdateAlertRuleMutation,
} from "@/lib/store/apis/alertingApi";

/**
 * The fallback view intentionally exposes operational metadata only.  It does
 * not render channel configuration or delivery payloads, which are scoped by
 * the authenticated alerting API.
 */
export default function AlertRulesView() {
	const { data, isLoading, error } = useGetAlertRulesQuery();
	const { data: historyData } = useGetAlertHistoryQuery();
	const [create] = useCreateAlertRuleMutation();
	const [update, { isLoading: isUpdating }] = useUpdateAlertRuleMutation();
	const [remove] = useDeleteAlertRuleMutation();
	const [name, setName] = useState("");
	const [event, setEvent] = useState("overdraft");
	const rules = data?.rules ?? [];
	const history = historyData?.history ?? [];

	return (
		<section className="mx-auto w-full max-w-5xl space-y-6 p-8" data-testid="alert-rules-view">
			<div>
				<h1 className="text-2xl font-semibold">Alert rules</h1>
				<p className="text-sm text-muted-foreground">Manage delivery policies and inspect their latest operational status.</p>
			</div>
			<form
				className="flex flex-wrap gap-3 rounded border p-4"
				onSubmit={async (e) => {
					e.preventDefault();
					if (!name.trim()) return;
					await create({ name: name.trim(), event, channel_ids: [], enabled: true }).unwrap();
					setName("");
				}}
			>
				<input className="rounded border px-2 py-1" value={name} onChange={(e) => setName(e.target.value)} placeholder="Budget overdraft" aria-label="Rule name" />
				<select className="rounded border px-2 py-1" value={event} onChange={(e) => setEvent(e.target.value)} aria-label="Rule event">
					<option value="overdraft">Overdraft</option>
					<option value="budget_limit">Budget limit</option>
					<option value="delivery_failure">Delivery failure</option>
				</select>
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
										onClick={() => void update({ id: rule.id, data: { name: rule.name, event: rule.event, channel_ids: rule.channel_ids, enabled: !rule.enabled } })}
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
