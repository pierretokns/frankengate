const jsonLd = {
	"@context": "https://schema.org",
	"@type": "WebPage",
	url: "https://pierretokns.github.io/frankengate/",
	name: "FrankenGate Documentation",
	description:
		"Documentation for FrankenGate, a Bifrost-compatible AI gateway with governed routing, analytics, and Kubernetes operations.",
	publisher: {
		"@type": "Organization",
		name: "FrankenGate",
		url: "https://github.com/pierretokns/frankengate",
		logo: {
			"@type": "ImageObject",
			url: "https://pierretokns.github.io/frankengate/logo.svg",
			width: 300,
			height: 60,
		},
		sameAs: ["https://github.com/pierretokns/frankengate"],
	},
	mainEntity: {
		"@type": "TechArticle",
		name: "FrankenGate Documentation",
		url: "https://pierretokns.github.io/frankengate/",
		headline: "FrankenGate Docs",
		description:
			"FrankenGate is a Bifrost-compatible AI gateway with governed provider routing and analytics.",
		inLanguage: "en",
	},
};

function injectJsonLd() {
	const script = document.createElement("script");
	script.type = "application/ld+json";
	script.text = JSON.stringify(jsonLd);

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", () => {
			document.head.appendChild(script);
		});
	} else {
		document.head.appendChild(script);
	}

	return () => {
		if (script.parentNode) {
			script.parentNode.removeChild(script);
		}
	};
}

// Call the function to inject JSON-LD
const cleanup = injectJsonLd();

// Cleanup when needed
// cleanup()
