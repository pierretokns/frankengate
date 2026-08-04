import { NoPermissionView } from "@/components/noPermissionView";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { PRODUCT_NAME } from "@/lib/constants/brand";
import { RenderProviderIcon } from "@/lib/constants/icons";
import { ProviderLabels, ProviderName } from "@/lib/constants/logs";
import {
	getErrorMessage,
	useGetAgentModelCardEvidenceQuery,
	useGetAgentModelCardQuery,
	useGetAgentModelCardVersionsQuery,
	useGetAgentModelCardsQuery,
} from "@/lib/store";
import {
	AgentModelCard,
	AgentModelCardEvidenceResponse,
	AgentModelCardFreshnessState,
	AgentModelCardSource,
	AgentModelCardSourceKind,
	AgentModelCardsListResponse,
	AgentModelCardVersionsResponse,
} from "@/lib/types/agentModelCards";
import { KnownProvider } from "@/lib/types/config";
import { cn } from "@/lib/utils";
import { RbacOperation, RbacResource, useRbac } from "@enterprise/lib";
import { AlertCircle, ChevronLeft, ChevronRight, RefreshCcw, Search, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

const PAGE_SIZE = 25;

const slug = (value: string) =>
	value
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-|-$/g, "") || "unknown";

const labelize = (value: string) =>
	value
		.split("_")
		.filter(Boolean)
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(" ");

const formatNumber = (value?: number) => (value == null ? "Not declared" : value.toLocaleString());

const formatPrice = (value?: number) => {
	if (value == null) return "Not declared";
	if (value === 0) return "$0";
	return `$${value.toPrecision(4)}`;
};

const sourceLabels: Record<string, string> = {
	key_config: "Key Config",
	live_list_models: "Live Models",
	datasheet_pricing: "Datasheet",
	model_parameters: "Parameters",
};

function providerLabel(provider: string) {
	return ProviderLabels[provider as ProviderName] || provider;
}

function buildSourceMap(sources: AgentModelCardSource[] | undefined) {
	return new Map((sources ?? []).map((source) => [source.kind, source]));
}

function freshnessRank(state: AgentModelCardFreshnessState | undefined) {
	switch (state) {
		case "stale":
			return 5;
		case "unknown":
			return 4;
		case "source_not_configured":
			return 3;
		case "local_cache_no_timestamp":
			return 2;
		case "shared_with_datasheet":
			return 1;
		case "fresh":
			return 0;
		default:
			return 4;
	}
}

function cardFreshness(card: AgentModelCard, sourceMap: Map<AgentModelCardSourceKind, AgentModelCardSource>) {
	const sourceStates = card.sources.map((source) => sourceMap.get(source)?.freshness).filter(Boolean) as AgentModelCardFreshnessState[];
	if (sourceStates.length === 0) {
		return { state: "unknown" as AgentModelCardFreshnessState, label: "Freshness Unknown" };
	}
	const state = sourceStates.reduce((worst, current) => (freshnessRank(current) > freshnessRank(worst) ? current : worst), sourceStates[0]);
	switch (state) {
		case "fresh":
			return { state, label: "Fresh" };
		case "stale":
			return { state, label: "Stale" };
		case "local_cache_no_timestamp":
			return { state, label: "Local Cache" };
		case "shared_with_datasheet":
			return { state, label: "Shared Freshness" };
		case "source_not_configured":
			return { state, label: "Source Missing" };
		default:
			return { state, label: "Freshness Unknown" };
	}
}

function trustState(card: AgentModelCard) {
	if (card.is_deprecated) {
		return { label: "Deprecated", variant: "warning" as const };
	}
	if (card.capability_state !== "known") {
		return { label: "Capability Unknown", variant: "outline" as const };
	}
	if (card.sources.includes("datasheet_pricing") && card.sources.includes("live_list_models")) {
		return { label: "Verified", variant: "success" as const };
	}
	if (card.sources.includes("live_list_models")) {
		return { label: "Observed", variant: "default" as const };
	}
	return { label: "Configured", variant: "secondary" as const };
}

function FreshnessBadge({
	card,
	sourceMap,
	className,
}: {
	card: AgentModelCard;
	sourceMap: Map<AgentModelCardSourceKind, AgentModelCardSource>;
	className?: string;
}) {
	const freshness = cardFreshness(card, sourceMap);
	const variant =
		freshness.state === "fresh" || freshness.state === "shared_with_datasheet"
			? "success"
			: freshness.state === "stale"
				? "destructive"
				: freshness.state === "unknown"
					? "outline"
					: "warning";
	return (
		<Badge
			variant={variant}
			className={className}
			data-testid={`agent-model-card-freshness-badge-${slug(card.provider)}-${slug(card.model)}`}
		>
			{freshness.label}
		</Badge>
	);
}

function TrustBadge({ card, className }: { card: AgentModelCard; className?: string }) {
	const trust = trustState(card);
	return (
		<Badge variant={trust.variant} className={className} data-testid={`agent-model-card-trust-badge-${slug(card.provider)}-${slug(card.model)}`}>
			{trust.label}
		</Badge>
	);
}

function AgentModelCardListSkeleton() {
	return (
		<div className="space-y-2" data-testid="agent-model-cards-list-loading">
			{Array.from({ length: 6 }).map((_, index) => (
				<div key={index} className="rounded-sm border p-3">
					<div className="flex items-center justify-between gap-3">
						<Skeleton className="h-4 w-40" />
						<Skeleton className="h-5 w-20" />
					</div>
					<Skeleton className="mt-3 h-3 w-56" />
					<div className="mt-3 flex gap-2">
						<Skeleton className="h-5 w-20" />
						<Skeleton className="h-5 w-24" />
					</div>
				</div>
			))}
		</div>
	);
}

function EmptyListState({ hasFilter }: { hasFilter: boolean }) {
	return (
		<div
			className="flex min-h-[320px] flex-col items-center justify-center rounded-sm border border-dashed p-8 text-center"
			data-testid="agent-model-cards-list-empty"
		>
			<Sparkles className="text-muted-foreground h-5 w-5" />
			<h2 className="mt-3 text-sm font-semibold">{hasFilter ? "No matching agent model cards" : "No agent model cards yet"}</h2>
			<p className="text-muted-foreground mt-1 max-w-sm text-sm">
				{hasFilter
					? "Adjust the search filter to inspect another provider or model."
					: "Cards appear here after the model catalog can compile visible provider models."}
			</p>
		</div>
	);
}

function ErrorState({ message, onRetry, testId }: { message: string; onRetry: () => void; testId: string }) {
	return (
		<div className="flex min-h-[320px] flex-col items-center justify-center rounded-sm border border-dashed p-8 text-center" data-testid={testId}>
			<AlertCircle className="text-destructive h-5 w-5" />
			<h2 className="mt-3 text-sm font-semibold">Unable to load agent model cards</h2>
			<p className="text-muted-foreground mt-1 max-w-md text-sm">{message}</p>
			<Button variant="outline" size="sm" className="mt-4" onClick={onRetry} data-testid={`${testId}-retry`}>
				<RefreshCcw className="h-4 w-4" />
				Retry
			</Button>
		</div>
	);
}

function SourceChips({ card, sourceMap }: { card: AgentModelCard; sourceMap: Map<AgentModelCardSourceKind, AgentModelCardSource> }) {
	if (card.sources.length === 0) {
		return <span className="text-muted-foreground text-xs">No sources</span>;
	}
	return (
		<TooltipProvider>
			<div className="flex flex-wrap gap-1.5">
				{card.sources.map((source) => {
					const sourceDetails = sourceMap.get(source);
					const label = sourceLabels[source] ?? labelize(source);
					return (
						<Tooltip key={source}>
							<TooltipTrigger asChild>
								<Badge variant="outline" data-testid={`agent-model-card-source-badge-${slug(card.provider)}-${slug(card.model)}-${slug(source)}`}>
									{label}
								</Badge>
							</TooltipTrigger>
							<TooltipContent side="bottom" className="max-w-xs">
								<div className="space-y-1 text-xs">
									<div>Freshness: {labelize(sourceDetails?.freshness ?? "unknown")}</div>
									<div>Revision: {sourceDetails?.revision ?? "unknown"}</div>
								</div>
							</TooltipContent>
						</Tooltip>
					);
				})}
			</div>
		</TooltipProvider>
	);
}

function CardListItem({
	card,
	sourceMap,
	selected,
	onSelect,
}: {
	card: AgentModelCard;
	sourceMap: Map<AgentModelCardSourceKind, AgentModelCardSource>;
	selected: boolean;
	onSelect: () => void;
}) {
	return (
		<button
			type="button"
			onClick={onSelect}
			className={cn(
				"w-full rounded-sm border p-3 text-left transition-colors",
				selected ? "border-primary bg-primary/5" : "hover:bg-accent/50 border-border",
			)}
			data-testid={`agent-model-card-row-${slug(card.provider)}-${slug(card.model)}`}
			aria-pressed={selected}
		>
			<div className="flex min-w-0 items-start justify-between gap-3">
				<div className="min-w-0">
					<div className="flex min-w-0 items-center gap-2">
						<RenderProviderIcon provider={card.provider as KnownProvider} size="sm" className="h-4 w-4 shrink-0" />
						<span className="truncate text-sm font-semibold">{card.model}</span>
					</div>
					<div className="text-muted-foreground mt-1 truncate text-xs">
						{providerLabel(card.provider)} · {card.base_model}
					</div>
				</div>
				<TrustBadge card={card} />
			</div>
			<div className="mt-3 flex flex-wrap gap-1.5">
				<FreshnessBadge card={card} sourceMap={sourceMap} />
				<Badge variant="secondary">{card.supported_request_types?.length ?? 0} operations</Badge>
			</div>
		</button>
	);
}

function DetailLoadingState() {
	return (
		<div className="h-full rounded-sm border p-5" data-testid="agent-model-card-detail-loading">
			<div className="flex items-start justify-between gap-4">
				<div className="space-y-3">
					<Skeleton className="h-5 w-56" />
					<Skeleton className="h-4 w-40" />
				</div>
				<Skeleton className="h-6 w-24" />
			</div>
			<div className="mt-6 grid grid-cols-3 gap-3">
				<Skeleton className="h-20" />
				<Skeleton className="h-20" />
				<Skeleton className="h-20" />
			</div>
			<Skeleton className="mt-6 h-40" />
		</div>
	);
}

function DetailEmptyState() {
	return (
		<div
			className="flex h-full min-h-[420px] flex-col items-center justify-center rounded-sm border border-dashed p-8 text-center"
			data-testid="agent-model-card-detail-empty"
		>
			<ShieldCheck className="text-muted-foreground h-5 w-5" />
			<h2 className="mt-3 text-sm font-semibold">Select an agent model card</h2>
			<p className="text-muted-foreground mt-1 max-w-sm text-sm">Choose a catalog entry to inspect provider mapping, source freshness, and trust metadata.</p>
		</div>
	);
}

function MetricBlock({ label, value, testId }: { label: string; value: string; testId: string }) {
	return (
		<div className="rounded-sm border p-3" data-testid={testId}>
			<div className="text-muted-foreground text-xs">{label}</div>
			<div className="mt-1 truncate font-mono text-sm font-semibold">{value}</div>
		</div>
	);
}

function DetailView({
	card,
	sourceMap,
	response,
	versions,
	evidence,
}: {
	card: AgentModelCard;
	sourceMap: Map<AgentModelCardSourceKind, AgentModelCardSource>;
	response: AgentModelCardsListResponse | undefined;
	versions: AgentModelCardVersionsResponse | undefined;
	evidence: AgentModelCardEvidenceResponse | undefined;
}) {
	const pricing = card.pricing;
	const sourceDetails = card.sources.map((source) => sourceMap.get(source)).filter(Boolean) as AgentModelCardSource[];
	return (
		<div className="flex h-full min-h-0 flex-col overflow-hidden rounded-sm border" data-testid="agent-model-card-detail">
			<div className="shrink-0 border-b p-5">
				<div className="flex items-start justify-between gap-4">
					<div className="min-w-0">
						<div className="flex min-w-0 items-center gap-2">
							<RenderProviderIcon provider={card.provider as KnownProvider} size="sm" className="h-5 w-5 shrink-0" />
							<h2 className="truncate text-lg font-semibold" data-testid="agent-model-card-detail-title">
								{card.model}
							</h2>
						</div>
						<div className="text-muted-foreground mt-1 text-sm" data-testid="agent-model-card-detail-provider">
							{providerLabel(card.provider)} · {card.base_model}
						</div>
					</div>
					<div className="flex flex-wrap justify-end gap-1.5">
						<TrustBadge card={card} />
						<FreshnessBadge card={card} sourceMap={sourceMap} />
					</div>
				</div>
				<div className="text-muted-foreground mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs">
					<span data-testid="agent-model-card-detail-revision">Revision {response?.revision.id ?? "unknown"}</span>
					<span data-testid="agent-model-card-detail-schema">Schema {response?.card_schema_version ?? "unknown"}</span>
				</div>
			</div>

			<div className="custom-scrollbar min-h-0 grow overflow-auto p-5">
				<div className="grid grid-cols-1 gap-3 md:grid-cols-3">
					<MetricBlock label="Context" value={formatNumber(card.limits?.context_length)} testId="agent-model-card-detail-context" />
					<MetricBlock label="Max Input" value={formatNumber(card.limits?.max_input_tokens)} testId="agent-model-card-detail-max-input" />
					<MetricBlock label="Max Output" value={formatNumber(card.limits?.max_output_tokens)} testId="agent-model-card-detail-max-output" />
				</div>

				<section className="mt-6" data-testid="agent-model-card-detail-mapping">
					<h3 className="text-sm font-semibold">Provider Mapping</h3>
					<div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
						<MetricBlock label="Requested Model" value={card.provider_mapping.requested_model} testId="agent-model-card-detail-requested-model" />
						<MetricBlock label="Wire Model" value={card.provider_mapping.wire_model} testId="agent-model-card-detail-wire-model" />
					</div>
				</section>

				<section className="mt-6" data-testid="agent-model-card-detail-sources">
					<h3 className="text-sm font-semibold">Sources</h3>
					<div className="mt-3">
						<SourceChips card={card} sourceMap={sourceMap} />
					</div>
					<div className="mt-3 divide-y rounded-sm border">
						{sourceDetails.length === 0 ? (
							<div className="text-muted-foreground p-3 text-sm">No source details are available.</div>
						) : (
							sourceDetails.map((source) => (
								<div key={source.kind} className="grid grid-cols-1 gap-2 p-3 text-sm md:grid-cols-[180px_1fr_140px]">
									<div className="font-medium">{sourceLabels[source.kind] ?? labelize(source.kind)}</div>
									<div className="text-muted-foreground truncate font-mono text-xs">{source.revision}</div>
									<div className="text-muted-foreground text-xs">{labelize(source.freshness)}</div>
								</div>
							))
						)}
					</div>
				</section>

				<section className="mt-6" data-testid="agent-model-card-detail-operations">
					<h3 className="text-sm font-semibold">Supported Operations</h3>
					<div className="mt-3 flex flex-wrap gap-1.5">
						{(card.supported_request_types ?? []).length === 0 ? (
							<span className="text-muted-foreground text-sm">No operations declared.</span>
						) : (
							card.supported_request_types?.map((requestType) => (
								<Badge key={requestType} variant="secondary">
									{labelize(requestType)}
								</Badge>
							))
						)}
					</div>
				</section>

				<section className="mt-6" data-testid="agent-model-card-detail-pricing">
					<h3 className="text-sm font-semibold">Pricing</h3>
					<div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
						<MetricBlock label="Input Token" value={formatPrice(pricing?.input_cost_per_token)} testId="agent-model-card-detail-input-price" />
						<MetricBlock label="Output Token" value={formatPrice(pricing?.output_cost_per_token)} testId="agent-model-card-detail-output-price" />
					</div>
				</section>

				<section className="mt-6" data-testid="agent-model-card-detail-evidence">
					<h3 className="text-sm font-semibold">History &amp; Evidence</h3>
					<div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
						<MetricBlock
							label="History"
							value={versions?.history_available ? `${versions.versions.length} versions` : "Current revision only"}
							testId="agent-model-card-detail-history"
						/>
						<MetricBlock
							label="Evidence"
							value={evidence?.evidence_available ? "Available" : "Unavailable"}
							testId="agent-model-card-detail-evidence-state"
						/>
						<MetricBlock
							label="Health"
							value={labelize(evidence?.health_state ?? "unknown")}
							testId="agent-model-card-detail-health-state"
						/>
					</div>
					{(versions?.reason_codes?.length ?? 0) > 0 || (evidence?.reason_codes?.length ?? 0) > 0 ? (
						<p className="text-muted-foreground mt-3 text-xs" data-testid="agent-model-card-detail-evidence-reasons">
							{[...(versions?.reason_codes ?? []), ...(evidence?.reason_codes ?? [])].join(" · ")}
						</p>
					) : null}
				</section>

				{(card.aliases ?? []).length > 0 && (
					<section className="mt-6" data-testid="agent-model-card-detail-aliases">
						<h3 className="text-sm font-semibold">Aliases</h3>
						<div className="mt-3 divide-y rounded-sm border">
							{card.aliases?.map((alias) => (
								<div key={`${alias.key_id}:${alias.alias}`} className="grid grid-cols-1 gap-2 p-3 text-sm md:grid-cols-[180px_1fr]">
									<div className="font-mono">{alias.alias}</div>
									<div className="text-muted-foreground truncate">{alias.model_id}</div>
								</div>
							))}
						</div>
					</section>
				)}
			</div>
		</div>
	);
}

function AgentModelCardsWorkspaceView() {
	const [search, setSearch] = useState("");
	const [offset, setOffset] = useState(0);
	const [selected, setSelected] = useState<{ provider: string; model: string } | null>(null);

	useEffect(() => {
		setOffset(0);
	}, [search]);

	const listQuery = useGetAgentModelCardsQuery({
		query: search.trim() || undefined,
		limit: PAGE_SIZE,
		offset,
		unfiltered: true,
	});

	const cards = useMemo(() => listQuery.data?.cards ?? [], [listQuery.data?.cards]);
	const sourceMap = useMemo(() => buildSourceMap(listQuery.data?.sources), [listQuery.data?.sources]);

	useEffect(() => {
		if (!listQuery.data) return;
		if (cards.length === 0) {
			setSelected(null);
			return;
		}
		if (!selected || !cards.some((card) => card.provider === selected.provider && card.model === selected.model)) {
			setSelected({ provider: cards[0].provider, model: cards[0].model });
		}
	}, [cards, listQuery.data, selected]);

	const detailQuery = useGetAgentModelCardQuery(
		{ provider: selected?.provider ?? "", model: selected?.model ?? "", unfiltered: true },
		{ skip: !selected },
	);
	const versionsQuery = useGetAgentModelCardVersionsQuery(
		{ provider: selected?.provider ?? "", model: selected?.model ?? "" },
		{ skip: !selected },
	);
	const evidenceQuery = useGetAgentModelCardEvidenceQuery(
		{ provider: selected?.provider ?? "", model: selected?.model ?? "" },
		{ skip: !selected },
	);

	const selectedCard = detailQuery.data?.card;

	return (
		<div className="no-padding-parent mx-auto flex h-[calc(100dvh-1rem)] min-h-0 w-full max-w-7xl flex-col overflow-hidden p-4" data-testid="agent-model-cards-page">
			<div className="mb-4 flex shrink-0 items-start justify-between gap-4">
				<div>
					<div className="text-muted-foreground text-xs font-medium">{PRODUCT_NAME}</div>
					<h1 className="text-xl font-semibold" data-testid="agent-model-cards-heading">
						Agent Model Cards
					</h1>
					<p className="text-muted-foreground mt-1 text-sm">Catalog trust, freshness, and provider mapping for routable models.</p>
				</div>
				<Button variant="outline" size="sm" onClick={() => listQuery.refetch()} data-testid="agent-model-cards-refresh-btn">
					<RefreshCcw className="h-4 w-4" />
					Refresh
				</Button>
			</div>

			<div className="grid min-h-0 grow grid-cols-1 gap-4 lg:grid-cols-[380px_1fr]">
				<div className="flex min-h-0 flex-col">
					<div className="mb-3 flex shrink-0 items-center gap-2">
						<div className="relative min-w-0 flex-1">
							<Search className="text-muted-foreground absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
							<Input
								aria-label="Search agent model cards"
								placeholder="Search provider or model..."
								value={search}
								onChange={(event) => setSearch(event.target.value)}
								className="pl-9"
								data-testid="agent-model-cards-search-input"
							/>
						</div>
					</div>

					<div className="custom-scrollbar min-h-0 grow overflow-auto pr-1" data-testid="agent-model-cards-list">
						{listQuery.isLoading && !listQuery.data ? (
							<AgentModelCardListSkeleton />
						) : listQuery.error ? (
							<ErrorState message={getErrorMessage(listQuery.error)} onRetry={listQuery.refetch} testId="agent-model-cards-list-error" />
						) : cards.length === 0 ? (
							<EmptyListState hasFilter={!!search.trim()} />
						) : (
							<div className="space-y-2">
								{cards.map((card) => (
									<CardListItem
										key={`${card.provider}:${card.model}`}
										card={card}
										sourceMap={sourceMap}
										selected={selected?.provider === card.provider && selected?.model === card.model}
										onSelect={() => setSelected({ provider: card.provider, model: card.model })}
									/>
								))}
							</div>
						)}
					</div>

					{(listQuery.data?.total ?? 0) > 0 && (
						<div className="mt-3 flex shrink-0 items-center justify-between text-xs" data-testid="agent-model-cards-pagination">
							<div className="text-muted-foreground">
								{offset + 1}-{Math.min(offset + PAGE_SIZE, listQuery.data?.total ?? 0)} of {(listQuery.data?.total ?? 0).toLocaleString()}
							</div>
							<div className="flex items-center gap-1">
								<Button
									variant="ghost"
									size="sm"
									onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
									disabled={offset === 0}
									data-testid="agent-model-cards-prev-btn"
									aria-label="Previous agent model card page"
								>
									<ChevronLeft className="h-4 w-4" />
								</Button>
								<Button
									variant="ghost"
									size="sm"
									onClick={() => setOffset(offset + PAGE_SIZE)}
									disabled={!listQuery.data?.has_more}
									data-testid="agent-model-cards-next-btn"
									aria-label="Next agent model card page"
								>
									<ChevronRight className="h-4 w-4" />
								</Button>
							</div>
						</div>
					)}
				</div>

				<div className="min-h-0">
					{!selected ? (
						<DetailEmptyState />
					) : detailQuery.isLoading && !detailQuery.data ? (
						<DetailLoadingState />
					) : detailQuery.error ? (
						<ErrorState message={getErrorMessage(detailQuery.error)} onRetry={detailQuery.refetch} testId="agent-model-card-detail-error" />
					) : selectedCard ? (
						<DetailView
							card={selectedCard}
							sourceMap={sourceMap}
							response={listQuery.data}
							versions={versionsQuery.data}
							evidence={evidenceQuery.data}
						/>
					) : (
						<DetailEmptyState />
					)}
				</div>
			</div>
		</div>
	);
}

export default function AgentModelCardsView() {
	const hasAccess = useRbac(RbacResource.ModelProvider, RbacOperation.View);

	if (!hasAccess) {
		return <NoPermissionView entity="agent model cards" />;
	}

	return <AgentModelCardsWorkspaceView />;
}
