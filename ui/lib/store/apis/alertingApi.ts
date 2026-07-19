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

export const alertingApi = baseApi.injectEndpoints({
	endpoints: (builder) => ({
		getAlertChannels: builder.query<{ channels: AlertChannel[] }, void>({ query: () => "/alerting/channels", providesTags: ["AlertChannels"] }),
		createAlertChannel: builder.mutation<AlertingState, Omit<AlertChannel, "id">>({ query: (body) => ({ url: "/alerting/channels", method: "POST", body }), invalidatesTags: ["AlertChannels", "AlertRules", "AlertHistory"] }),
		updateAlertChannel: builder.mutation<AlertingState, { id: string; data: Omit<AlertChannel, "id"> }>({ query: ({ id, data }) => ({ url: `/alerting/channels/${id}`, method: "PUT", body: data }), invalidatesTags: ["AlertChannels", "AlertRules", "AlertHistory"] }),
		deleteAlertChannel: builder.mutation<void, string>({ query: (id) => ({ url: `/alerting/channels/${id}`, method: "DELETE" }), invalidatesTags: ["AlertChannels", "AlertRules"] }),
		getAlertRules: builder.query<{ rules: AlertRule[] }, void>({ query: () => "/alerting/rules", providesTags: ["AlertRules"] }),
		createAlertRule: builder.mutation<AlertingState, Omit<AlertRule, "id">>({ query: (body) => ({ url: "/alerting/rules", method: "POST", body }), invalidatesTags: ["AlertRules", "AlertChannels", "AlertHistory"] }),
		updateAlertRule: builder.mutation<AlertingState, { id: string; data: Omit<AlertRule, "id"> }>({ query: ({ id, data }) => ({ url: `/alerting/rules/${id}`, method: "PUT", body: data }), invalidatesTags: ["AlertRules", "AlertChannels", "AlertHistory"] }),
		deleteAlertRule: builder.mutation<void, string>({ query: (id) => ({ url: `/alerting/rules/${id}`, method: "DELETE" }), invalidatesTags: ["AlertRules"] }),
		getAlertHistory: builder.query<{ history: AlertDelivery[] }, void>({ query: () => "/alerting/history", providesTags: ["AlertHistory"] }),
	}),
});

export const { useGetAlertChannelsQuery, useCreateAlertChannelMutation, useUpdateAlertChannelMutation, useDeleteAlertChannelMutation, useGetAlertRulesQuery, useCreateAlertRuleMutation, useUpdateAlertRuleMutation, useDeleteAlertRuleMutation, useGetAlertHistoryQuery } = alertingApi;
