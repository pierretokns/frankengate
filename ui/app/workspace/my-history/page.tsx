import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scrollArea";
import {
	type EvalPlan,
	type EvalSuggestion,
	getErrorMessage,
	useCreateMyEvalPlanMutation,
	useGetMyEvalSuggestionsQuery,
	useGetMyPromptHistoryQuery,
} from "@/lib/store";
import { formatDistanceToNow } from "date-fns";
import { AlertCircle, ArrowRight, FlaskConical, History, Loader2, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";

function PromptHistory() {
	const { data, error, isLoading } = useGetMyPromptHistoryQuery({ limit: 100, offset: 0 });

	if (isLoading) {
		return (
			<div className="text-muted-foreground flex items-center gap-2 text-sm">
				<Loader2 className="size-4 animate-spin" />
				Loading your history…
			</div>
		);
	}
	if (error) {
		return (
			<Alert variant="destructive">
				<AlertCircle className="size-4" />
				<AlertDescription>{getErrorMessage(error)}</AlertDescription>
			</Alert>
		);
	}
	if (!data?.logs.length) {
		return <p className="text-muted-foreground text-sm">Your prompt history will appear here after your first attributed request.</p>;
	}

	return (
		<ScrollArea className="h-[32rem] pr-4">
			<div className="space-y-3">
				{data.logs.map((entry) => (
					<div key={entry.id} className="bg-muted/35 rounded-lg border p-3">
						<div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
							<Badge variant={entry.status === "success" ? "secondary" : "destructive"}>{entry.status}</Badge>
							<span className="font-medium">{entry.model}</span>
							<span className="text-muted-foreground">{formatDistanceToNow(new Date(entry.timestamp), { addSuffix: true })}</span>
						</div>
						<p className="line-clamp-4 text-sm">{entry.content_summary || "Prompt content is unavailable or redacted."}</p>
						<p className="text-muted-foreground mt-2 font-mono text-[11px]">{entry.id}</p>
					</div>
				))}
			</div>
		</ScrollArea>
	);
}

function EvalGuide({ suggestion }: { suggestion: EvalSuggestion }) {
	const [answers, setAnswers] = useState<Record<string, string>>({});
	const [plan, setPlan] = useState<EvalPlan | null>(null);
	const [createPlan, { isLoading, error }] = useCreateMyEvalPlanMutation();

	const canCreate = useMemo(() => Object.values(answers).some((answer) => answer.trim().length > 0), [answers]);
	const handleCreate = async () => {
		const result = await createPlan({ suggestion_id: suggestion.id, answers }).unwrap();
		setPlan(result);
	};

	if (plan) {
		return (
			<div className="space-y-4 rounded-lg border p-4">
				<div>
					<p className="text-muted-foreground text-xs uppercase">Draft task</p>
					<p className="font-mono text-sm">{plan.task_id}</p>
				</div>
				<div>
					<p className="font-medium">Scenario</p>
					<p className="text-muted-foreground text-sm">{plan.scenario}</p>
				</div>
				<div>
					<p className="font-medium">Success</p>
					<p className="text-muted-foreground text-sm">{plan.success}</p>
				</div>
				<div>
					<p className="font-medium">Runtime boundary</p>
					<p className="text-muted-foreground text-sm">{plan.runtime}</p>
				</div>
				<ol className="text-muted-foreground list-decimal space-y-1 pl-5 text-sm">
					{plan.next_steps.map((step) => (
						<li key={step}>{step}</li>
					))}
				</ol>
				<Button variant="outline" size="sm" onClick={() => setPlan(null)}>
					Revise answers
				</Button>
			</div>
		);
	}

	return (
		<div className="space-y-4">
			{suggestion.questions.map((question) => (
				<label key={question.id} className="block space-y-1.5">
					<span className="text-sm font-medium">{question.question}</span>
					<span className="text-muted-foreground block text-xs">{question.why}</span>
					<Input
						value={answers[question.id] ?? ""}
						onChange={(event) => setAnswers((current) => ({ ...current, [question.id]: event.target.value }))}
					/>
				</label>
			))}
			{error ? <p className="text-destructive text-sm">{getErrorMessage(error)}</p> : null}
			<Button onClick={handleCreate} disabled={!canCreate || isLoading}>
				{isLoading ? <Loader2 className="size-4 animate-spin" /> : <ArrowRight className="size-4" />}
				Create a draft eval plan
			</Button>
		</div>
	);
}

function EvalSuggestions() {
	const { data, error, isLoading } = useGetMyEvalSuggestionsQuery();
	const [selectedID, setSelectedID] = useState<string | null>(null);
	const selected = data?.suggestions.find((suggestion) => suggestion.id === selectedID);

	if (isLoading) {
		return (
			<div className="text-muted-foreground flex items-center gap-2 text-sm">
				<Loader2 className="size-4 animate-spin" />
				Analyzing your traces…
			</div>
		);
	}
	if (error) {
		return (
			<Alert variant="destructive">
				<AlertCircle className="size-4" />
				<AlertDescription>{getErrorMessage(error)}</AlertDescription>
			</Alert>
		);
	}
	if (!data?.suggestions.length) {
		return (
			<p className="text-muted-foreground text-sm">
				Once you have attributed traces, this guide will suggest a first eval grounded in your real usage.
			</p>
		);
	}

	return (
		<div className="space-y-4">
			<Alert>
				<ShieldCheck className="size-4" />
				<AlertDescription>{data.method.trace_use}</AlertDescription>
			</Alert>
			<div className="grid gap-3">
				{data.suggestions.map((suggestion) => (
					<button
						key={suggestion.id}
						type="button"
						onClick={() => setSelectedID(suggestion.id)}
						className={`rounded-lg border p-4 text-left transition-colors ${selectedID === suggestion.id ? "border-primary bg-primary/5" : "hover:bg-muted/40"}`}
					>
						<div className="flex items-start justify-between gap-3">
							<div>
								<p className="font-medium">{suggestion.name}</p>
								<p className="text-muted-foreground mt-1 text-sm">{suggestion.description}</p>
							</div>
							<Badge variant="outline">{suggestion.evidence.matching_traces} traces</Badge>
						</div>
						<p className="text-muted-foreground mt-3 text-xs">{suggestion.evidence.explanation}</p>
					</button>
				))}
			</div>
			{selected ? <EvalGuide key={selected.id} suggestion={selected} /> : null}
		</div>
	);
}

export default function MyHistoryPage() {
	return (
		<div className="h-full overflow-auto p-6">
			<div className="mx-auto max-w-7xl space-y-6">
				<div>
					<h1 className="text-2xl font-semibold">My history & eval guide</h1>
					<p className="text-muted-foreground mt-1">
						Review your own prompts and turn recurring trace patterns into controlled evaluation plans.
					</p>
				</div>
				<div className="grid gap-6 lg:grid-cols-2">
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2">
								<History className="size-5" />
								My prompt history
							</CardTitle>
							<CardDescription>Only requests attributed to your authenticated user identity.</CardDescription>
						</CardHeader>
						<CardContent>
							<PromptHistory />
						</CardContent>
					</Card>
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2">
								<FlaskConical className="size-5" />
								Suggested evals
							</CardTitle>
							<CardDescription>Explainable recommendations derived from your recent traces.</CardDescription>
						</CardHeader>
						<CardContent>
							<EvalSuggestions />
						</CardContent>
					</Card>
				</div>
			</div>
		</div>
	);
}