import { useState } from "react";
import { useCreateAlertChannelMutation, useDeleteAlertChannelMutation, useGetAlertChannelsQuery } from "@/lib/store/apis/alertingApi";

export default function AlertChannelsView() {
	const { data, isLoading, error } = useGetAlertChannelsQuery();
	const [create] = useCreateAlertChannelMutation();
	const [remove] = useDeleteAlertChannelMutation();
	const [name, setName] = useState("");
	const [type, setType] = useState("webhook");
	const [accountId, setAccountId] = useState("");
	const [apiToken, setApiToken] = useState("");
	const [from, setFrom] = useState("");
	const [recipients, setRecipients] = useState("");
	const channels = data?.channels ?? [];
	return <section className="mx-auto w-full max-w-5xl space-y-6 p-8" data-testid="alert-channels-view"><h1 className="text-2xl font-semibold">Alert channels</h1><form className="flex flex-wrap gap-3 rounded border p-4" onSubmit={async (e) => { e.preventDefault(); if (!name.trim()) return; const config: Record<string, string> = type === "cloudflare_email" ? { account_id: accountId.trim(), api_token: apiToken, from: from.trim(), recipients: recipients.trim() } : {}; await create({ name: name.trim(), type, enabled: true, config }).unwrap(); setName(""); setAccountId(""); setApiToken(""); setFrom(""); setRecipients(""); }}><input className="rounded border px-2 py-1" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ops notifications" /><select className="rounded border px-2 py-1" value={type} onChange={(e) => setType(e.target.value)}><option value="webhook">Webhook</option><option value="sns">SNS</option><option value="email">Email (SES)</option><option value="cloudflare_email">Cloudflare Email</option></select>{type === "cloudflare_email" && <><input className="rounded border px-2 py-1" value={accountId} onChange={(e) => setAccountId(e.target.value)} placeholder="Cloudflare account ID" required /><input className="rounded border px-2 py-1" value={apiToken} onChange={(e) => setApiToken(e.target.value)} placeholder="Cloudflare API token" type="password" required /><input className="rounded border px-2 py-1" value={from} onChange={(e) => setFrom(e.target.value)} placeholder="From address" type="email" required /><input className="rounded border px-2 py-1" value={recipients} onChange={(e) => setRecipients(e.target.value)} placeholder="Recipients (comma-separated)" required /></>}<button className="rounded bg-primary px-3 py-1.5 text-primary-foreground" type="submit">Add channel</button></form>{isLoading ? <p>Loading channels…</p> : error ? <p role="alert">Unable to load alert channels.</p> : <ul className="divide-y rounded border">{channels.map((channel) => <li className="flex justify-between p-3" key={channel.id}><span><strong>{channel.name}</strong> <small>{channel.type}</small></span><button type="button" onClick={() => void remove(channel.id)}>Remove</button></li>)}</ul>}</section>;
}
