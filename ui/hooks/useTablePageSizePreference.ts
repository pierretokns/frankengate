import { useEffect, useState } from "react";

const DEFAULT_PAGE_SIZE = 25;
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 200] as const;

export function useTablePageSizePreference(storageKey: string, fallback = DEFAULT_PAGE_SIZE): [number, (value: number) => void] {
	const [pageSize, setPageSize] = useState(fallback);

	useEffect(() => {
		const stored = window.localStorage.getItem(storageKey);
		const parsed = stored === null ? NaN : Number(stored);
		if (PAGE_SIZE_OPTIONS.includes(parsed as (typeof PAGE_SIZE_OPTIONS)[number])) {
			setPageSize(parsed);
		}
	}, [storageKey]);

	const updatePageSize = (value: number) => {
		if (!PAGE_SIZE_OPTIONS.includes(value as (typeof PAGE_SIZE_OPTIONS)[number])) return;
		setPageSize(value);
		window.localStorage.setItem(storageKey, String(value));
	};

	return [pageSize, updatePageSize];
}

export { PAGE_SIZE_OPTIONS };