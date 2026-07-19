import { useState } from "react";
import { useCreateAlertRuleMutation, useDeleteAlertRuleMutation, useGetAlertRulesQuery } from "@/lib/store/apis/alertingApi";

export default function AlertRulesView() {
	const { data, isLoading, error } = useGetAlertRulesQuery();
	const [create] = useCreateAlertRuleMutation();
	const [remove] = useDeleteAlertRuleMutation();
	const [name, setName] = useState("");
	const [event, setEvent] = useState("overdraft");
	const rules = data?.rules ?? [];
	return <section className="mx-auto w-full max-w-5xl space-y-6 p-8" data-testid="alert-rules-view"><h1 className="text-2xl font-semibold">Alert rules</h1><form className="flex flex-wrap gap-3 rounded border p-4" onSubmit={async (e) => { e.preventDefault(); if (!name.trim()) return; await create({ name: name.trim(), event, channel_ids: [], enabled: true }).unwrap(); setName(""); }}><input className="rounded border px-2 py-1" value={name} onChange={(e) => setName(e.target.value)} placeholder="Budget overdraft" /><select className="rounded border px-2 py-1" value={event} onChange={(e) => setEvent(e.target.value)}><option value="overdraft">Overdraft</option><option value="budget_limit">Budget limit</option><option value="delivery_failure">Delivery failure</option></select><button className="rounded bg-primary px-3 py-1.5 text-primary-foreground" type="submit">Add rule</button></form>{isLoading ? <p>Loading rules…</p> : error ? <p role="alert">Unable to load alert rules.</p> : <ul className="divide-y rounded border">{rules.map((rule) => <li className="flex justify-between p-3" key={rule.id}><span><strong>{rule.name}</strong> <small>{rule.event}</small></span><span><small>{rule.enabled ? "enabled" : "disabled"}</small> <button type="button" onClick={() => void remove(rule.id)}>Remove</button></span></li>)}</ul>}</section>;
}
