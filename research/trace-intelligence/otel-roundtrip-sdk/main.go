// Command otel-roundtrip-sdk emits a content-minimized span manifest through
// the real OpenTelemetry Go SDK and its OTLP/HTTP exporter.
//
// The manifest is generated in a temporary directory by
// otel_collector_roundtrip.py. It contains no prompt content or authority
// values and must never be committed.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"runtime"
	"strconv"
	"sync"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"
)

const sdkVersion = "1.43.0"

type anyValue struct {
	StringValue *string  `json:"stringValue,omitempty"`
	IntValue    *string  `json:"intValue,omitempty"`
	DoubleValue *float64 `json:"doubleValue,omitempty"`
	BoolValue   *bool    `json:"boolValue,omitempty"`
}

type manifestAttribute struct {
	Key   string   `json:"key"`
	Value anyValue `json:"value"`
}

type manifestLink struct {
	TraceID    string              `json:"traceId"`
	SpanID     string              `json:"spanId"`
	Attributes []manifestAttribute `json:"attributes"`
}

type manifestSpan struct {
	TraceID           string              `json:"traceId"`
	SpanID            string              `json:"spanId"`
	ParentSpanID      string              `json:"parentSpanId,omitempty"`
	Name              string              `json:"name"`
	StartTimeUnixNano string              `json:"startTimeUnixNano"`
	EndTimeUnixNano   string              `json:"endTimeUnixNano"`
	Attributes        []manifestAttribute `json:"attributes"`
	Links             []manifestLink      `json:"links,omitempty"`
	StatusError       bool                `json:"statusError"`
}

type manifest struct {
	SchemaVersion      string              `json:"schemaVersion"`
	ResourceSchemaURL  string              `json:"resourceSchemaUrl"`
	ResourceAttributes []manifestAttribute `json:"resourceAttributes"`
	ScopeName          string              `json:"scopeName"`
	ScopeVersion       string              `json:"scopeVersion"`
	Spans              []manifestSpan      `json:"spans"`
}

type expectedID struct {
	traceID trace.TraceID
	spanID  trace.SpanID
}

type fixedIDGenerator struct {
	mu       sync.Mutex
	expected []expectedID
	next     int
	err      error
}

func (g *fixedIDGenerator) take(traceID *trace.TraceID) (trace.TraceID, trace.SpanID) {
	g.mu.Lock()
	defer g.mu.Unlock()
	if g.next >= len(g.expected) {
		g.err = errors.New("OpenTelemetry SDK requested more IDs than manifest spans")
		return trace.TraceID{}, trace.SpanID{}
	}
	item := g.expected[g.next]
	g.next++
	if traceID != nil && *traceID != item.traceID {
		g.err = fmt.Errorf(
			"parent trace ID does not match manifest at span index %d",
			g.next-1,
		)
	}
	return item.traceID, item.spanID
}

func (g *fixedIDGenerator) NewIDs(context.Context) (trace.TraceID, trace.SpanID) {
	return g.take(nil)
}

func (g *fixedIDGenerator) NewSpanID(_ context.Context, traceID trace.TraceID) trace.SpanID {
	_, spanID := g.take(&traceID)
	return spanID
}

type recordingErrorHandler struct {
	mu     sync.Mutex
	errors []string
}

func (h *recordingErrorHandler) Handle(err error) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.errors = append(h.errors, err.Error())
}

func (h *recordingErrorHandler) count() int {
	h.mu.Lock()
	defer h.mu.Unlock()
	return len(h.errors)
}

func attributes(values []manifestAttribute) ([]attribute.KeyValue, error) {
	result := make([]attribute.KeyValue, 0, len(values))
	for _, item := range values {
		value := item.Value
		switch {
		case value.StringValue != nil:
			result = append(result, attribute.String(item.Key, *value.StringValue))
		case value.IntValue != nil:
			parsed, err := strconv.ParseInt(*value.IntValue, 10, 64)
			if err != nil {
				return nil, fmt.Errorf("attribute %q has invalid int: %w", item.Key, err)
			}
			result = append(result, attribute.Int64(item.Key, parsed))
		case value.DoubleValue != nil:
			result = append(result, attribute.Float64(item.Key, *value.DoubleValue))
		case value.BoolValue != nil:
			result = append(result, attribute.Bool(item.Key, *value.BoolValue))
		default:
			return nil, fmt.Errorf("attribute %q has no supported value", item.Key)
		}
	}
	return result, nil
}

func parseUnixNano(value string) (time.Time, error) {
	nanos, err := strconv.ParseInt(value, 10, 64)
	if err != nil {
		return time.Time{}, err
	}
	return time.Unix(0, nanos), nil
}

func spanContext(traceIDHex, spanIDHex string) (trace.SpanContext, error) {
	traceID, err := trace.TraceIDFromHex(traceIDHex)
	if err != nil {
		return trace.SpanContext{}, err
	}
	spanID, err := trace.SpanIDFromHex(spanIDHex)
	if err != nil {
		return trace.SpanContext{}, err
	}
	return trace.NewSpanContext(trace.SpanContextConfig{
		TraceID:    traceID,
		SpanID:     spanID,
		TraceFlags: trace.FlagsSampled,
		Remote:     true,
	}), nil
}

func loadManifest(path string) (manifest, []expectedID, error) {
	var input manifest
	handle, err := os.Open(path)
	if err != nil {
		return input, nil, err
	}
	defer handle.Close()
	decoder := json.NewDecoder(handle)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&input); err != nil {
		return input, nil, err
	}
	if input.SchemaVersion != "frankengate-otel-sdk-manifest-v1" {
		return input, nil, fmt.Errorf("unsupported manifest schema %q", input.SchemaVersion)
	}
	if len(input.Spans) == 0 {
		return input, nil, errors.New("manifest contains no spans")
	}
	expected := make([]expectedID, 0, len(input.Spans))
	for index, item := range input.Spans {
		spanCtx, err := spanContext(item.TraceID, item.SpanID)
		if err != nil {
			return input, nil, fmt.Errorf("span %d has invalid IDs: %w", index, err)
		}
		expected = append(expected, expectedID{
			traceID: spanCtx.TraceID(),
			spanID:  spanCtx.SpanID(),
		})
	}
	return input, expected, nil
}

func run(manifestPath, endpoint string) error {
	input, expected, err := loadManifest(manifestPath)
	if err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	exporter, err := otlptracehttp.New(
		ctx,
		otlptracehttp.WithEndpointURL(endpoint),
		otlptracehttp.WithInsecure(),
		otlptracehttp.WithTimeout(3*time.Second),
		otlptracehttp.WithRetry(otlptracehttp.RetryConfig{Enabled: false}),
	)
	if err != nil {
		return err
	}
	resourceAttrs, err := attributes(input.ResourceAttributes)
	if err != nil {
		return err
	}
	res := resource.NewWithAttributes(input.ResourceSchemaURL, resourceAttrs...)
	generator := &fixedIDGenerator{expected: expected}
	errorHandler := &recordingErrorHandler{}
	otel.SetErrorHandler(errorHandler)
	provider := sdktrace.NewTracerProvider(
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
		sdktrace.WithIDGenerator(generator),
		sdktrace.WithBatcher(
			exporter,
			sdktrace.WithBatchTimeout(100*time.Millisecond),
			sdktrace.WithMaxExportBatchSize(512),
			sdktrace.WithMaxQueueSize(1024),
		),
	)
	tracer := provider.Tracer(
		input.ScopeName,
		trace.WithInstrumentationVersion(input.ScopeVersion),
	)

	for index, item := range input.Spans {
		spanAttrs, err := attributes(item.Attributes)
		if err != nil {
			return fmt.Errorf("span %d attributes: %w", index, err)
		}
		start, err := parseUnixNano(item.StartTimeUnixNano)
		if err != nil {
			return fmt.Errorf("span %d start time: %w", index, err)
		}
		end, err := parseUnixNano(item.EndTimeUnixNano)
		if err != nil {
			return fmt.Errorf("span %d end time: %w", index, err)
		}
		parentContext := context.Background()
		if item.ParentSpanID != "" {
			parent, err := spanContext(item.TraceID, item.ParentSpanID)
			if err != nil {
				return fmt.Errorf("span %d parent: %w", index, err)
			}
			parentContext = trace.ContextWithRemoteSpanContext(parentContext, parent)
		}
		links := make([]trace.Link, 0, len(item.Links))
		for linkIndex, itemLink := range item.Links {
			linkContext, err := spanContext(itemLink.TraceID, itemLink.SpanID)
			if err != nil {
				return fmt.Errorf("span %d link %d: %w", index, linkIndex, err)
			}
			linkAttrs, err := attributes(itemLink.Attributes)
			if err != nil {
				return fmt.Errorf(
					"span %d link %d attributes: %w",
					index,
					linkIndex,
					err,
				)
			}
			links = append(links, trace.Link{
				SpanContext: linkContext,
				Attributes:  linkAttrs,
			})
		}
		_, span := tracer.Start(
			parentContext,
			item.Name,
			trace.WithTimestamp(start),
			trace.WithSpanKind(trace.SpanKindInternal),
			trace.WithAttributes(spanAttrs...),
			trace.WithLinks(links...),
		)
		if item.StatusError {
			span.SetStatus(codes.Error, "redacted failure")
		}
		span.End(trace.WithTimestamp(end))
	}

	if err := provider.ForceFlush(ctx); err != nil {
		return fmt.Errorf("force flush: %w", err)
	}
	if err := provider.Shutdown(ctx); err != nil {
		return fmt.Errorf("shutdown: %w", err)
	}
	if generator.err != nil {
		return generator.err
	}
	if generator.next != len(expected) {
		return fmt.Errorf(
			"OpenTelemetry SDK generated %d IDs for %d spans",
			generator.next,
			len(expected),
		)
	}
	if errorHandler.count() != 0 {
		return fmt.Errorf("OpenTelemetry SDK reported %d export errors", errorHandler.count())
	}
	fmt.Printf(
		"{\"go_toolchain\":%q,\"sdk\":\"go.opentelemetry.io/otel\",\"sdk_version\":%q,\"spans_ended\":%d}\n",
		runtime.Version(),
		sdkVersion,
		len(input.Spans),
	)
	return nil
}

func main() {
	manifestPath := flag.String("manifest", "", "content-minimized JSON manifest")
	endpoint := flag.String("endpoint", "", "OTLP/HTTP endpoint URL")
	flag.Parse()
	if *manifestPath == "" || *endpoint == "" {
		fmt.Fprintln(os.Stderr, "--manifest and --endpoint are required")
		os.Exit(2)
	}
	if err := run(*manifestPath, *endpoint); err != nil {
		fmt.Fprintf(os.Stderr, "otel-roundtrip-sdk: %v\n", err)
		os.Exit(1)
	}
}
