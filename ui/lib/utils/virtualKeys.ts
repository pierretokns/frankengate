const MASKED_VIRTUAL_KEY = "••••••••";

/**
 * Format a virtual-key secret without assuming redacted API responses contain
 * the key value. The governance API intentionally omits `value` from list and
 * detail responses, so absent or malformed values must remain safely masked.
 */
export function formatVirtualKeySecret(value: unknown, revealed: boolean): string {
	if (typeof value !== "string" || value.length === 0) {
		return MASKED_VIRTUAL_KEY;
	}
	if (revealed) {
		return value;
	}
	if (value.length <= 8) {
		return MASKED_VIRTUAL_KEY;
	}
	return value.slice(0, 8) + "•".repeat(value.length - 8);
}