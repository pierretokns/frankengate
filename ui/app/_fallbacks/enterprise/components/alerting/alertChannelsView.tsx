import { useState, type FormEvent } from "react";
import { useCreateAlertChannelMutation, useDeleteAlertChannelMutation, useGetAlertChannelsQuery } from "@/lib/store/apis/alertingApi";

export default function AlertChannelsView() {
	const { data, isLoading, error } = useGetAlertChannelsQuery();
	const [create] = useCreateAlertChannelMutation();
	const [remove] = useDeleteAlertChannelMutation();
	const [name, setName] = useState("");
	const [type, setType] = useState("webhook");
	const [url, setURL] = useState("");
	const [topicARN, setTopicARN] = useState("");
	const [region, setRegion] = useState("");
	const [subject, setSubject] = useState("");
	const [from, setFrom] = useState("");
	const [recipients, setRecipients] = useState("");
	const [signingKey, setSigningKey] = useState("");
	const channels = data?.channels ?? [];
	const reset = () => {
		setName(""); setURL(""); setTopicARN(""); setRegion(""); setSubject("");
		setFrom(""); setRecipients(""); setSigningKey("");
	};
	const submit = async (event: FormEvent<HTMLFormElement>) => {
		event.preventDefault();
		if (!name.trim()) return;
		const config: Record<string, string> = {};
		if (type === "webhook") Object.assign(config, { url: url.trim(), signing_key: signingKey });
		if (type === "sns") Object.assign(config, { topic_arn: topicARN.trim(), region: region.trim(), subject: subject.trim() });
		if (type === "email") Object.assign(config, { from: from.trim(), recipients: recipients.trim(), region: region.trim(), subject: subject.trim() });
		await create({ name: name.trim(), type, enabled: true, config }).unwrap();
		reset();
	};
	return <section className="mx-auto w-full max-w-5xl space-y-6 p-8" data-testid="alert-channels-view">
		<h1 className="text-2xl font-semibold">Alert channels</h1>
		<form className="flex flex-wrap gap-3 rounded border p-4" onSubmit={submit}>
			<input className="rounded border px-2 py-1" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ops notifications" required />
			<select className="rounded border px-2 py-1" value={type} onChange={(e) => setType(e.target.value)}><option value="webhook">Webhook</option><option value="sns">SNS</option><option value="email">Email (SES)</option></select>
			{type === "webhook" && <><input className="rounded border px-2 py-1" value={url} onChange={(e) => setURL(e.target.value)} placeholder="https://alerts.example/hook" type="url" required /><input className="rounded border px-2 py-1" value={signingKey} onChange={(e) => setSigningKey(e.target.value)} placeholder="Signing key (optional)" type="password" /></>}
			{type === "sns" && <><input className="rounded border px-2 py-1" value={topicARN} onChange={(e) => setTopicARN(e.target.value)} placeholder="arn:aws:sns:..." required /><input className="rounded border px-2 py-1" value={region} onChange={(e) => setRegion(e.target.value)} placeholder="us-east-1" required /><input className="rounded border px-2 py-1" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject (optional)" /></>}
			{type === "email" && <><input className="rounded border px-2 py-1" value={from} onChange={(e) => setFrom(e.target.value)} placeholder="From address" type="email" required /><input className="rounded border px-2 py-1" value={recipients} onChange={(e) => setRecipients(e.target.value)} placeholder="Recipients (comma-separated)" required /><input className="rounded border px-2 py-1" value={region} onChange={(e) => setRegion(e.target.value)} placeholder="us-east-1" required /><input className="rounded border px-2 py-1" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject (optional)" /></>}
			<button className="rounded bg-primary px-3 py-1.5 text-primary-foreground" type="submit">Add channel</button>
		</form>
		{isLoading ? <p>Loading channels…</p> : error ? <p role="alert">Unable to load alert channels.</p> : <ul className="divide-y rounded border">{channels.map((channel) => <li className="flex justify-between p-3" key={channel.id}><span><strong>{channel.name}</strong> <small>{channel.type}</small></span><button type="button" onClick={() => void remove(channel.id)}>Remove</button></li>)}</ul>}
	</section>;
}
