import {
	AgentModelCardDetailRequest,
	AgentModelCardDetailResponse,
	AgentModelCardsListRequest,
	AgentModelCardsListResponse,
} from "@/lib/types/agentModelCards";
import { baseApi } from "./baseApi";

const buildAgentModelCardParams = (params?: AgentModelCardsListRequest) => {
	const searchParams = new URLSearchParams();
	if (params?.query) searchParams.set("query", params.query);
	if (params?.provider) searchParams.set("provider", params.provider);
	if (params?.limit != null) searchParams.set("limit", String(params.limit));
	if (params?.offset != null) searchParams.set("offset", String(params.offset));
	if (params?.unfiltered != null) searchParams.set("unfiltered", String(params.unfiltered));
	const qs = searchParams.toString();
	return qs ? `?${qs}` : "";
};

export const agentModelCardsApi = baseApi.injectEndpoints({
	endpoints: (builder) => ({
		getAgentModelCards: builder.query<AgentModelCardsListResponse, AgentModelCardsListRequest | void>({
			query: (params) => `/v1/agent-model-cards${buildAgentModelCardParams(params || undefined)}`,
			providesTags: ["AgentModelCards"],
		}),
		getAgentModelCard: builder.query<AgentModelCardDetailResponse, AgentModelCardDetailRequest>({
			query: ({ provider, model, unfiltered }) => {
				const searchParams = new URLSearchParams();
				searchParams.set("provider", provider);
				searchParams.set("model", model);
				if (unfiltered != null) searchParams.set("unfiltered", String(unfiltered));
				return `/v1/agent-model-cards/detail?${searchParams.toString()}`;
			},
			providesTags: (_result, _error, { provider, model }) => [{ type: "AgentModelCards", id: `${provider}:${model}` }],
		}),
	}),
});

export const { useGetAgentModelCardsQuery, useGetAgentModelCardQuery } = agentModelCardsApi;
