import type { LogEntry, Pagination } from "@/lib/types/logs";
import { baseApi } from "./baseApi";

export interface EvalGuidedQuestion {
	id: string;
	question: string;
	why: string;
}

export interface EvalSuggestion {
	id: string;
	name: string;
	description: string;
	priority: number;
	capability: string;
	example_request?: string;
	recommended_check: string;
	verifier: "deterministic" | "semantic" | "hybrid";
	evidence: {
		matching_traces: number;
		sample_trace_ids?: string[];
		explanation: string;
	};
	questions: EvalGuidedQuestion[];
}

export interface EvalAssistantResponse {
	trace_count: number;
	suggestions: EvalSuggestion[];
	method: {
		trace_use: string;
		workflow: string;
		interchange: string;
		source_version: string;
		source_reference: string;
	};
}

export interface EvalPlan {
	suggestion_id: string;
	task_id: string;
	capability: string;
	scenario: string;
	runtime: string;
	dependencies: string;
	success: string;
	verifier: string;
	answers: Record<string, string>;
	next_steps: string[];
}

export const selfServiceEvalsApi = baseApi.injectEndpoints({
	endpoints: (builder) => ({
		getMyPromptHistory: builder.query<{ logs: LogEntry[]; pagination: Pagination; has_logs: boolean }, { limit?: number; offset?: number }>(
			{
				query: ({ limit = 50, offset = 0 }) => ({
					url: "/me/prompt-history",
					params: { limit, offset },
				}),
				providesTags: ["Logs"],
			},
		),
		getMyEvalSuggestions: builder.query<EvalAssistantResponse, void>({
			query: () => "/me/eval-suggestions",
			providesTags: ["Logs"],
		}),
		createMyEvalPlan: builder.mutation<EvalPlan, { suggestion_id: string; answers: Record<string, string> }>({
			query: (body) => ({
				url: "/me/eval-plan",
				method: "POST",
				body,
			}),
		}),
	}),
});

export const { useGetMyPromptHistoryQuery, useGetMyEvalSuggestionsQuery, useCreateMyEvalPlanMutation } = selfServiceEvalsApi;