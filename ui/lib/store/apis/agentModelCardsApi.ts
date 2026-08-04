import {
	AgentModelCardDetailRequest,
	AgentModelCardDetailResponse,
	AgentModelCardMetadataResponse,
	AgentModelCardDiffResponse,
	AgentModelCardEvidenceResponse,
	AgentModelCardVersionsResponse,
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
		getAgentModelCardMetadata: builder.query<AgentModelCardMetadataResponse, AgentModelCardsListRequest | void>({
			query: (params) => `/v1/agent-model-cards/metadata${buildAgentModelCardParams(params || undefined)}`,
			providesTags: ["AgentModelCards"],
		}),
		getAgentModelCardVersions: builder.query<AgentModelCardVersionsResponse, AgentModelCardDetailRequest>({
			query: ({ provider, model }) => `/v1/agent-model-cards/versions?provider=${encodeURIComponent(provider)}&model=${encodeURIComponent(model)}`,
			providesTags: (_result, _error, { provider, model }) => [{ type: "AgentModelCards", id: `${provider}:${model}:versions` }],
		}),
		getAgentModelCardEvidence: builder.query<AgentModelCardEvidenceResponse, AgentModelCardDetailRequest>({
			query: ({ provider, model }) => `/v1/agent-model-cards/evidence?provider=${encodeURIComponent(provider)}&model=${encodeURIComponent(model)}`,
			providesTags: (_result, _error, { provider, model }) => [{ type: "AgentModelCards", id: `${provider}:${model}:evidence` }],
		}),
		getAgentModelCardDiff: builder.query<AgentModelCardDiffResponse, AgentModelCardDetailRequest & { fromRevision: string }>({
			query: ({ provider, model, fromRevision }) => `/v1/agent-model-cards/diff?provider=${encodeURIComponent(provider)}&model=${encodeURIComponent(model)}&from_revision=${encodeURIComponent(fromRevision)}`,
			providesTags: (_result, _error, { provider, model, fromRevision }) => [{ type: "AgentModelCards", id: `${provider}:${model}:diff:${fromRevision}` }],
		}),
	}),
});

export const { useGetAgentModelCardsQuery, useGetAgentModelCardQuery, useGetAgentModelCardMetadataQuery, useGetAgentModelCardVersionsQuery, useGetAgentModelCardEvidenceQuery, useGetAgentModelCardDiffQuery } = agentModelCardsApi;
