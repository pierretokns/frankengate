import { useGetAlertHistoryQuery } from "@/lib/store/apis/alertingApi";

export default function AlertHistoryView() {
	const { data, isLoading, error } = useGetAlertHistoryQuery();
	const history = data?.history ?? [];
	return <section className="mx-auto w-full max-w-5xl space-y-6 p-8" data-testid="alert-history-view"><h1 className="text-2xl font-semibold">Alert history</h1>{isLoading ? <p>Loading delivery history…</p> : error ? <p role="alert">Unable to load alert history.</p> : <table className="w-full rounded border text-left text-sm"><thead><tr className="border-b"><th className="p-3">Created</th><th className="p-3">Rule</th><th className="p-3">Status</th><th className="p-3">Error</th></tr></thead><tbody>{history.map((delivery) => <tr className="border-b" key={delivery.id}><td className="p-3">{delivery.created_at}</td><td className="p-3">{delivery.rule_id}</td><td className="p-3">{delivery.status}</td><td className="p-3">{delivery.error ?? "—"}</td></tr>)}</tbody></table>}</section>;
}
