import { baseApi } from "./baseApi";

export type AlertChannel = { id: string; name: string; type: "webhook" | "sns" | "email" | string; config?: Record<string, string>; enabled: boolean };
export type AlertRule = {
	id: string;
	name: string;
	event: string;
	channel_ids: string[];
	enabled: boolean;
	scope?: "global" | "team" | "user" | string;
	scope_id?: string;
	approval_required?: boolean;
	approved?: boolean;
};
export type AlertDelivery = { id: string; rule_id: string; status: string; error?: string; created_at: string };
export type AlertingState = { channels: AlertChannel[]; rules: AlertRule[]; history: AlertDelivery[] };
/** Optional dashboard projection. Empty scope preserves the global view. */
export type AlertingScope = { scope?: "global" | "team" | "user"; scope_id?: string };

const scopeQuery = (value?: AlertingScope) => {
	if (!value?.scope) return "";
	const params = new URLSearchParams({ scope: value.scope });
	if (value.scope !== "global" && value.scope_id?.trim()) params.set("scope_id", value.scope_id.trim());
	return `?${params.toString()}`;
};

export const alertingApi = baseApi.injectEndpoints({
	endpoints: (builder) => ({
		getAlertChannels: builder.query<{ channels: AlertChannel[] }, AlertingScope | void>({ query: (scope) => `/alerting/channels${scopeQuery(scope)}`, providesTags: ["AlertChannels"] }),
		createAlertChannel: builder.mutation<AlertingState, Omit<AlertChannel, "id">>({ query: (body) => ({ url: "/alerting/channels", method: "POST", body }), invalidatesTags: ["AlertChannels", "AlertRules", "AlertHistory"] }),
		updateAlertChannel: builder.mutation<AlertingState, { id: string; data: Omit<AlertChannel, "id"> }>({ query: ({ id, data }) => ({ url: `/alerting/channels/${id}`, method: "PUT", body: data }), invalidatesTags: ["AlertChannels", "AlertRules", "AlertHistory"] }),
		deleteAlertChannel: builder.mutation<void, string>({ query: (id) => ({ url: `/alerting/channels/${id}`, method: "DELETE" }), invalidatesTags: ["AlertChannels", "AlertRules"] }),
		getAlertRules: builder.query<{ rules: AlertRule[] }, AlertingScope | void>({ query: (scope) => `/alerting/rules${scopeQuery(scope)}`, providesTags: ["AlertRules"] }),
		createAlertRule: builder.mutation<AlertingState, Omit<AlertRule, "id">>({ query: (body) => ({ url: "/alerting/rules", method: "POST", body }), invalidatesTags: ["AlertRules", "AlertChannels", "AlertHistory"] }),
		updateAlertRule: builder.mutation<AlertingState, { id: string; data: Omit<AlertRule, "id"> }>({ query: ({ id, data }) => ({ url: `/alerting/rules/${id}`, method: "PUT", body: data }), invalidatesTags: ["AlertRules", "AlertChannels", "AlertHistory"] }),
		deleteAlertRule: builder.mutation<void, string>({ query: (id) => ({ url: `/alerting/rules/${id}`, method: "DELETE" }), invalidatesTags: ["AlertRules"] }),
		getAlertHistory: builder.query<{ history: AlertDelivery[] }, AlertingScope | void>({ query: (scope) => `/alerting/history${scopeQuery(scope)}`, providesTags: ["AlertHistory"] }),
	}),
});

export const { useGetAlertChannelsQuery, useCreateAlertChannelMutation, useUpdateAlertChannelMutation, useDeleteAlertChannelMutation, useGetAlertRulesQuery, useCreateAlertRuleMutation, useUpdateAlertRuleMutation, useDeleteAlertRuleMutation, useGetAlertHistoryQuery } = alertingApi;
