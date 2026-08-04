export type AgentModelCardSourceKind = "key_config" | "live_list_models" | "datasheet_pricing" | "model_parameters" | string;

export type AgentModelCardFreshnessState =
	| "fresh"
	| "stale"
	| "unknown"
	| "local_cache_no_timestamp"
	| "shared_with_datasheet"
	| "source_not_configured"
	| string;

export type AgentModelCapabilityState = "known" | "unknown" | string;

export interface AgentModelCardRevision {
	id: string;
	card_count: number;
}

export interface AgentModelCardSource {
	kind: AgentModelCardSourceKind;
	revision: string;
	freshness: AgentModelCardFreshnessState;
	details?: Record<string, string>;
}

export interface AgentModelProviderMapping {
	provider: string;
	requested_model: string;
	wire_model: string;
	canonical_model?: string;
}

export interface AgentModelCardAlias {
	alias: string;
	key_id?: string;
	model_id: string;
	model_name?: string;
	model_family?: string;
	description?: string;
}

export interface AgentModelCardLimits {
	context_length?: number;
	max_input_tokens?: number;
	max_output_tokens?: number;
}

export interface AgentModelCardPricing {
	mode?: string;
	input_cost_per_token?: number;
	output_cost_per_token?: number;
	cache_read_input_token_cost?: number;
	cache_creation_input_token_cost?: number;
	input_cost_per_image?: number;
	output_cost_per_image?: number;
	search_context_cost_per_query?: number;
	code_interpreter_cost_per_session?: number;
}

export interface AgentModelCard {
	provider: string;
	model: string;
	base_model: string;
	capability_state: AgentModelCapabilityState;
	is_deprecated?: boolean;
	sources: AgentModelCardSourceKind[];
	provider_mapping: AgentModelProviderMapping;
	aliases?: AgentModelCardAlias[];
	supported_request_types?: string[];
	supported_parameters?: string[];
	architecture?: unknown;
	limits?: AgentModelCardLimits;
	pricing?: AgentModelCardPricing;
	routable_key_ids?: string[];
	live_key_ids?: string[];
	unfiltered_live_key_ids?: string[];
}

export interface AgentModelCardsListResponse {
	schema_version: string;
	card_schema_version: string;
	revision: AgentModelCardRevision;
	source_precedence: AgentModelCardSourceKind[];
	sources: AgentModelCardSource[];
	unknown_behavior: {
		capability_state: string;
		admission: string;
		pricing: string;
	};
	deprecated_behavior: {
		visibility: string;
		admission: string;
	};
	cards: AgentModelCard[];
	total: number;
	limit: number;
	offset: number;
	has_more: boolean;
}

export interface AgentModelCardDetailResponse {
	schema_version: string;
	card_schema_version: string;
	revision: AgentModelCardRevision;
	card: AgentModelCard;
}

export interface AgentModelCardsListRequest {
	query?: string;
	provider?: string;
	limit?: number;
	offset?: number;
	unfiltered?: boolean;
}

export interface AgentModelCardDetailRequest {
	provider: string;
	model: string;
	unfiltered?: boolean;
}
