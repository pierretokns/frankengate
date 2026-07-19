"use client";

import { Button } from "@/components/ui/button";
import { Users, UserRound } from "lucide-react";

export type GovernanceScope = "team" | "user";

interface GovernanceScopeToggleProps {
	value: GovernanceScope;
	onChange: (scope: GovernanceScope) => void;
}

/**
 * A compact, URL-backed scope switch for the two governance views operators
 * use most often. The parent owns navigation and filters, so this component
 * never invents or caches metrics of its own.
 */
export function GovernanceScopeToggle({ value, onChange }: GovernanceScopeToggleProps) {
	return (
		<div className="flex items-center gap-1" role="group" aria-label="Governance dashboard scope" data-testid="dashboard-governance-scope">
			<span className="text-muted-foreground mr-1 text-xs">Scope</span>
			<Button
				variant={value === "team" ? "secondary" : "ghost"}
				size="sm"
				aria-pressed={value === "team"}
				dataTestId="dashboard-governance-scope-team"
				onClick={() => onChange("team")}
			>
				<Users /> Team
			</Button>
			<Button
				variant={value === "user" ? "secondary" : "ghost"}
				size="sm"
				aria-pressed={value === "user"}
				dataTestId="dashboard-governance-scope-user"
				onClick={() => onChange("user")}
			>
				<UserRound /> User
			</Button>
		</div>
	);
}
