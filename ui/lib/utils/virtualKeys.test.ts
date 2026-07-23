import { describe, expect, it } from "vitest";
import { formatVirtualKeySecret } from "./virtualKeys";

describe("formatVirtualKeySecret", () => {
	it.each([undefined, null, "", 42, {}])("safely masks an absent or malformed value (%p)", (value) => {
		expect(formatVirtualKeySecret(value, false)).toBe("••••••••");
		expect(formatVirtualKeySecret(value, true)).toBe("••••••••");
	});

	it("does not expose short secrets while masked", () => {
		expect(formatVirtualKeySecret("short", false)).toBe("••••••••");
	});

	it("preserves only the identifying prefix of a masked secret", () => {
		expect(formatVirtualKeySecret("sk-bf-12345678", false)).toBe("sk-bf-12••••••");
	});

	it("returns a valid secret when explicitly revealed", () => {
		expect(formatVirtualKeySecret("sk-bf-12345678", true)).toBe("sk-bf-12345678");
	});
});