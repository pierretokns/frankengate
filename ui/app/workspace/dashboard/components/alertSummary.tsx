"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { useGetAlertHistoryQuery, useGetAlertRulesQuery } from "@/lib/store";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

/**
 * Compact operational summary for the dashboard header.  Alert history is
 * already scoped by the authenticated alerting handler; this component only
 * derives a presentation summary and never exposes payloads or channel config.
 */
export function AlertSummary() {
	const { data: historyData, isError: historyError } = useGetAlertHistoryQuery();
	const { data: rulesData } = useGetAlertRulesQuery();

	const deliveries = historyData?.history ?? [];
	const cutoff = Date.now() - 24 * 60 * 60 * 1000;
	const recent = deliveries.filter((delivery) => {
		const timestamp = Date.parse(delivery.created_at);
		return Number.isFinite(timestamp) && timestamp >= cutoff;
	});
	const failures = recent.filter((delivery) => delivery.status.toLowerCase() === "failed");
	const enabledRules = (rulesData?.rules ?? []).filter((rule) => rule.enabled).length;

	if (historyError) {
		return (
			<Alert variant="warning" className="w-auto max-w-sm py-2">
				<AlertTriangle />
				<AlertTitle>Alert status unavailable</AlertTitle>
				<AlertDescription>Alert history could not be loaded for this session.</AlertDescription>
			</Alert>
		);
	}

	return (
		<div className="flex items-center gap-2" data-testid="dashboard-alert-summary" aria-label="Alert summary">
			{failures.length > 0 ? (
				<Badge variant="destructive" title={`${failures.length} failed alert deliveries in the last 24 hours`}>
					<AlertTriangle /> {failures.length} failed alerts
				</Badge>
			) : (
				<Badge variant="success" title="No failed alert deliveries in the last 24 hours">
					<CheckCircle2 /> Alerts healthy
				</Badge>
			)}
			<Badge variant="outline" title={`${enabledRules} enabled alerting rules`}>
				{enabledRules} active {enabledRules === 1 ? "rule" : "rules"}
			</Badge>
		</div>
	);
}
