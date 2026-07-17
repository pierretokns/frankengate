// Package streaming provides functionality for accumulating streaming chunks and other chunk-related workflows
package streaming

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"hash"
	"io"
	"strings"
	"sync"
	"time"

	schemas "github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/modelcatalog"
)

// getAccumulatorID extracts the ID for accumulator lookup from context.
// Returns the value of BifrostContextKeyAccumulatorID.
func getAccumulatorID(ctx *schemas.BifrostContext) (string, bool) {
	if id, ok := ctx.Value(schemas.BifrostContextKeyAccumulatorID).(string); ok && id != "" {
		return id, true
	}
	return "", false
}

// Accumulator manages accumulation of streaming chunks
type Accumulator struct {
	logger schemas.Logger

	streamAccumulators sync.Map // Track accumulators by request ID (atomic)
	// endedStreamIDs prevents late gate calls after force cleanup from
	// recreating an orphan accumulator. CreateStreamAccumulator clears the
	// tombstone when a request ID is intentionally reused.
	endedStreamIDs sync.Map // request ID -> time.Time tombstone

	chatStreamChunkPool          sync.Pool // Pool for reusing StreamChunk structs
	responsesStreamChunkPool     sync.Pool // Pool for reusing ResponsesStreamChunk structs
	audioStreamChunkPool         sync.Pool // Pool for reusing AudioStreamChunk structs
	transcriptionStreamChunkPool sync.Pool // Pool for reusing TranscriptionStreamChunk structs
	imageStreamChunkPool         sync.Pool // Pool for reusing ImageStreamChunk structs

	pricingManager *modelcatalog.ModelCatalog

	stopCleanup   chan struct{}
	cleanupWg     sync.WaitGroup
	cleanupOnce   sync.Once
	ttl           time.Duration
	cleanupTicker *time.Ticker
	options       AccumulatorOptions
}

// AccumulatorOptions configures stream capture retention behavior.
type AccumulatorOptions struct {
	Limits AccumulatorLimits
	Hooks  AccumulatorHooks
}

// AccumulatorHooks exposes retention changes to metrics collectors.
type AccumulatorHooks struct {
	OnRetainedBytes func(StreamRetentionEvent)
}

// AccumulatorLimits bounds how much per-stream payload the accumulator retains.
// Zero values keep the corresponding purpose unlimited for compatibility.
type AccumulatorLimits struct {
	ChatMaxRetainedBytes           int64
	ChatMaxDuration                time.Duration
	ResponsesMaxRetainedBytes      int64
	ResponsesMaxDuration           time.Duration
	AudioMaxRetainedBytes          int64
	AudioMaxDuration               time.Duration
	TranscriptionMaxRetainedBytes  int64
	TranscriptionMaxDuration       time.Duration
	ImageMaxRetainedBytes          int64
	ImageMaxDuration               time.Duration
	RawResponseMaxBytes            int64
	RawResponseMaxDuration         time.Duration
	PassthroughMaxRetainedBytes    int64
	PassthroughMaxDuration         time.Duration
	PassthroughMaxHeaderCount      int
	PassthroughMaxHeaderNameBytes  int
	PassthroughMaxHeaderValueBytes int
	PassthroughMaxHeaderTotalBytes int64
}

const (
	defaultStreamCaptureMaxBytes          int64 = 4 << 20
	defaultLargeStreamCaptureMaxBytes     int64 = 16 << 20
	defaultRawResponseCaptureMaxBytes     int64 = 1 << 20
	defaultStreamCaptureMaxDuration             = 10 * time.Minute
	defaultPassthroughMaxHeaderCount            = 128
	defaultPassthroughMaxHeaderNameBytes        = 256
	defaultPassthroughMaxHeaderValueBytes       = 8 << 10
	defaultPassthroughMaxHeaderTotalBytes int64 = 64 << 10
	metadataDedupeMaxEntries                    = 256
)

// DefaultAccumulatorOptions returns conservative production stream-retention limits.
// NewAccumulator uses these defaults; NewAccumulatorWithOptions preserves explicit
// zero values for callers that intentionally opt into unlimited compatibility mode.
func DefaultAccumulatorOptions() AccumulatorOptions {
	return AccumulatorOptions{
		Limits: AccumulatorLimits{
			ChatMaxRetainedBytes:           defaultStreamCaptureMaxBytes,
			ChatMaxDuration:                defaultStreamCaptureMaxDuration,
			ResponsesMaxRetainedBytes:      defaultStreamCaptureMaxBytes,
			ResponsesMaxDuration:           defaultStreamCaptureMaxDuration,
			AudioMaxRetainedBytes:          defaultLargeStreamCaptureMaxBytes,
			AudioMaxDuration:               defaultStreamCaptureMaxDuration,
			TranscriptionMaxRetainedBytes:  defaultStreamCaptureMaxBytes,
			TranscriptionMaxDuration:       defaultStreamCaptureMaxDuration,
			ImageMaxRetainedBytes:          defaultLargeStreamCaptureMaxBytes,
			ImageMaxDuration:               defaultStreamCaptureMaxDuration,
			RawResponseMaxBytes:            defaultRawResponseCaptureMaxBytes,
			RawResponseMaxDuration:         defaultStreamCaptureMaxDuration,
			PassthroughMaxRetainedBytes:    defaultLargeStreamCaptureMaxBytes,
			PassthroughMaxDuration:         defaultStreamCaptureMaxDuration,
			PassthroughMaxHeaderCount:      defaultPassthroughMaxHeaderCount,
			PassthroughMaxHeaderNameBytes:  defaultPassthroughMaxHeaderNameBytes,
			PassthroughMaxHeaderValueBytes: defaultPassthroughMaxHeaderValueBytes,
			PassthroughMaxHeaderTotalBytes: defaultPassthroughMaxHeaderTotalBytes,
		},
	}
}

// Options returns the accumulator retention configuration.
func (a *Accumulator) Options() AccumulatorOptions {
	if a == nil {
		return AccumulatorOptions{}
	}
	return a.options
}

// getChatStreamChunk gets a chat stream chunk from the pool
func (a *Accumulator) getChatStreamChunk() *ChatStreamChunk {
	return a.chatStreamChunkPool.Get().(*ChatStreamChunk)
}

// putChatStreamChunk returns a chat stream chunk to the pool
func (a *Accumulator) putChatStreamChunk(chunk *ChatStreamChunk) {
	chunk.Timestamp = time.Time{}
	chunk.Delta = nil
	chunk.Cost = nil
	chunk.SemanticCacheDebug = nil
	chunk.ErrorDetails = nil
	chunk.FinishReason = nil
	chunk.TokenUsage = nil
	chunk.RawResponse = nil
	chunk.rawResponseCandidate = nil
	chunk.captureRawResponse = false
	a.chatStreamChunkPool.Put(chunk)
}

// GetAudioStreamChunk gets an audio stream chunk from the pool
func (a *Accumulator) getAudioStreamChunk() *AudioStreamChunk {
	return a.audioStreamChunkPool.Get().(*AudioStreamChunk)
}

// PutAudioStreamChunk returns an audio stream chunk to the pool
func (a *Accumulator) putAudioStreamChunk(chunk *AudioStreamChunk) {
	chunk.Timestamp = time.Time{}
	chunk.Delta = nil
	chunk.Cost = nil
	chunk.SemanticCacheDebug = nil
	chunk.ErrorDetails = nil
	chunk.FinishReason = nil
	chunk.TokenUsage = nil
	chunk.RawResponse = nil
	chunk.rawResponseCandidate = nil
	chunk.captureRawResponse = false
	a.audioStreamChunkPool.Put(chunk)
}

// getTranscriptionStreamChunk gets a transcription stream chunk from the pool
func (a *Accumulator) getTranscriptionStreamChunk() *TranscriptionStreamChunk {
	return a.transcriptionStreamChunkPool.Get().(*TranscriptionStreamChunk)
}

// putTranscriptionStreamChunk returns a transcription stream chunk to the pool
func (a *Accumulator) putTranscriptionStreamChunk(chunk *TranscriptionStreamChunk) {
	chunk.Timestamp = time.Time{}
	chunk.Delta = nil
	chunk.Cost = nil
	chunk.SemanticCacheDebug = nil
	chunk.ErrorDetails = nil
	chunk.FinishReason = nil
	chunk.TokenUsage = nil
	chunk.RawResponse = nil
	chunk.rawResponseCandidate = nil
	chunk.captureRawResponse = false
	a.transcriptionStreamChunkPool.Put(chunk)
}

// getResponsesStreamChunk gets a responses stream chunk from the pool
func (a *Accumulator) getResponsesStreamChunk() *ResponsesStreamChunk {
	return a.responsesStreamChunkPool.Get().(*ResponsesStreamChunk)
}

// putResponsesStreamChunk returns a responses stream chunk to the pool
func (a *Accumulator) putResponsesStreamChunk(chunk *ResponsesStreamChunk) {
	chunk.Timestamp = time.Time{}
	chunk.StreamResponse = nil
	chunk.Cost = nil
	chunk.SemanticCacheDebug = nil
	chunk.ErrorDetails = nil
	chunk.FinishReason = nil
	chunk.TokenUsage = nil
	chunk.RawResponse = nil
	chunk.rawResponseCandidate = nil
	chunk.captureRawResponse = false
	a.responsesStreamChunkPool.Put(chunk)
}

// getImageStreamChunk gets an image stream chunk from the pool
func (a *Accumulator) getImageStreamChunk() *ImageStreamChunk {
	return a.imageStreamChunkPool.Get().(*ImageStreamChunk)
}

// putImageStreamChunk returns an image stream chunk to the pool
func (a *Accumulator) putImageStreamChunk(chunk *ImageStreamChunk) {
	chunk.Timestamp = time.Time{}
	chunk.Delta = nil
	chunk.FinishReason = nil
	chunk.ErrorDetails = nil
	chunk.ChunkIndex = 0
	chunk.ImageIndex = 0
	chunk.Cost = nil
	chunk.SemanticCacheDebug = nil
	chunk.TokenUsage = nil
	chunk.RawResponse = nil
	chunk.rawResponseCandidate = nil
	chunk.captureRawResponse = false
	a.imageStreamChunkPool.Put(chunk)
}

// createStreamAccumulator creates a new stream accumulator for a request
// StartTimestamp is set to current time if not provided via CreateStreamAccumulator
func (a *Accumulator) createStreamAccumulator(requestID string) *StreamAccumulator {
	now := time.Now()
	sc := &StreamAccumulator{
		RequestID:                  requestID,
		ChatStreamChunks:           make([]*ChatStreamChunk, 0),
		ResponsesStreamChunks:      make([]*ResponsesStreamChunk, 0),
		ImageStreamChunks:          make([]*ImageStreamChunk, 0),
		TranscriptionStreamChunks:  make([]*TranscriptionStreamChunk, 0),
		AudioStreamChunks:          make([]*AudioStreamChunk, 0),
		ChatChunksSeen:             make(map[int]struct{}),
		ResponsesChunksSeen:        make(map[int]struct{}),
		TranscriptionChunksSeen:    make(map[int]struct{}),
		AudioChunksSeen:            make(map[int]struct{}),
		ImageChunksSeen:            make(map[string]struct{}),
		MaxChatChunkIndex:          -1,
		MaxResponsesChunkIndex:     -1,
		MaxTranscriptionChunkIndex: -1,
		MaxAudioChunkIndex:         -1,
		TerminalErrorChunkIndex:    -1,
		TerminalResponseChunkIndex: -1,
		IsComplete:                 false,
		mu:                         sync.Mutex{},
		Timestamp:                  now,
		StartTimestamp:             now, // Set default StartTimestamp for proper TTFT/latency calculation
		gateState:                  StreamStateActive,
		gatePausedAt:               -1,
		cancelWatchDone:            make(chan struct{}),
		parent:                     a,
	}
	sc.gateCond = sync.NewCond(&sc.mu)
	a.streamAccumulators.Store(requestID, sc)
	return sc
}

func shouldCaptureRawResponse(ctx *schemas.BifrostContext) bool {
	if capture, ok := ctx.Value(schemas.BifrostContextKeyCaptureRawResponse).(bool); ok {
		return capture
	}
	return true
}

func (sa *StreamAccumulator) markRawResponseDroppedLocked(reason string) {
	sa.capture.RawResponse.Mode = StreamCaptureModeDrop
	sa.capture.RawResponse.Reason = reason
}

func (sa *StreamAccumulator) recordRetentionEventLocked(purpose StreamCapturePurpose, state StreamCapturePurposeMetadata) {
	sa.pendingRetentionEvents = append(sa.pendingRetentionEvents, StreamRetentionEvent{
		RequestID:     sa.RequestID,
		Purpose:       purpose,
		Mode:          state.Mode,
		Reason:        state.Reason,
		RetainedBytes: state.RetainedBytes,
		DroppedBytes:  state.DroppedBytes,
		ChunksSeen:    state.ChunksSeen,
		DigestSHA256:  state.DigestSHA256,
	})
}

func (a *Accumulator) flushRetentionEvents(requestID string) {
	if requestID == "" || a.options.Hooks.OnRetainedBytes == nil {
		return
	}
	value, ok := a.streamAccumulators.Load(requestID)
	if !ok {
		return
	}
	accumulator := value.(*StreamAccumulator)
	accumulator.mu.Lock()
	events := append([]StreamRetentionEvent(nil), accumulator.pendingRetentionEvents...)
	accumulator.pendingRetentionEvents = nil
	accumulator.mu.Unlock()

	for _, event := range events {
		a.options.Hooks.OnRetainedBytes(event)
	}
}

func (sa *StreamAccumulator) clearRetainedRawResponsesLocked() {
	for _, chunk := range sa.ChatStreamChunks {
		chunk.RawResponse = nil
	}
	for _, chunk := range sa.ResponsesStreamChunks {
		chunk.RawResponse = nil
	}
	for _, chunk := range sa.AudioStreamChunks {
		chunk.RawResponse = nil
	}
	for _, chunk := range sa.TranscriptionStreamChunks {
		chunk.RawResponse = nil
	}
	for _, chunk := range sa.ImageStreamChunks {
		chunk.RawResponse = nil
	}
}

func (a *Accumulator) captureRawResponse(requestID string, ctx *schemas.BifrostContext, raw interface{}, timestamp time.Time) *string {
	if raw == nil {
		return nil
	}
	accumulator := a.getOrCreateStreamAccumulator(requestID)
	accumulator.mu.Lock()
	defer accumulator.mu.Unlock()
	return a.captureRawResponseLocked(accumulator, shouldCaptureRawResponse(ctx), raw, timestamp)
}

type rawCaptureResult struct {
	bytes    int64
	retained string
}

type rawCaptureWriter struct {
	state       *StreamCapturePurposeMetadata
	digest      *hash.Hash
	bufferLimit int64
	bytes       int64
	builder     strings.Builder
}

func (w *rawCaptureWriter) Write(p []byte) (int, error) {
	if len(p) == 0 {
		return 0, nil
	}
	w.bytes += int64(len(p))
	if w.state != nil && w.digest != nil {
		writeCaptureDigest(w.state, w.digest, p)
	}
	w.bufferBytes(p)
	return len(p), nil
}

func (w *rawCaptureWriter) WriteString(s string) (int, error) {
	if s == "" {
		return 0, nil
	}
	w.bytes += int64(len(s))
	if w.state != nil && w.digest != nil {
		writeCaptureDigestString(w.state, w.digest, s)
	}
	w.bufferString(s)
	return len(s), nil
}

func (w *rawCaptureWriter) remainingBuffer() int {
	if w.bufferLimit < 0 {
		return lenMax
	}
	if w.bufferLimit <= int64(w.builder.Len()) {
		return 0
	}
	remaining := w.bufferLimit - int64(w.builder.Len())
	if remaining > int64(lenMax) {
		return lenMax
	}
	return int(remaining)
}

func (w *rawCaptureWriter) bufferBytes(p []byte) {
	remaining := w.remainingBuffer()
	if remaining <= 0 {
		return
	}
	if len(p) > remaining {
		p = p[:remaining]
	}
	_, _ = w.builder.Write(p)
}

func (w *rawCaptureWriter) bufferString(s string) {
	remaining := w.remainingBuffer()
	if remaining <= 0 {
		return
	}
	if len(s) > remaining {
		s = s[:remaining]
	}
	_, _ = w.builder.WriteString(s)
}

const lenMax = int(^uint(0) >> 1)

func scanRawCaptureValue(raw interface{}, state *StreamCapturePurposeMetadata, digest *hash.Hash, bufferLimit int64) rawCaptureResult {
	writer := &rawCaptureWriter{state: state, digest: digest, bufferLimit: bufferLimit}
	writeRawCaptureValue(writer, raw)
	return rawCaptureResult{
		bytes:    writer.bytes,
		retained: writer.builder.String(),
	}
}

func writeRawCaptureValue(writer *rawCaptureWriter, raw interface{}) {
	switch v := raw.(type) {
	case nil:
		return
	case string:
		_, _ = writer.WriteString(v)
	case *string:
		if v != nil {
			_, _ = writer.WriteString(*v)
		}
	case []byte:
		_, _ = writer.Write(v)
	case *[]byte:
		if v != nil {
			_, _ = writer.Write(*v)
		}
	case json.RawMessage:
		_, _ = writer.Write([]byte(v))
	case *json.RawMessage:
		if v != nil {
			_, _ = writer.Write([]byte(*v))
		}
	default:
		_, _ = fmt.Fprint(writer, raw)
	}
}

func (a *Accumulator) captureRawResponseLocked(accumulator *StreamAccumulator, capture bool, raw interface{}, timestamp time.Time) *string {
	if raw == nil {
		return nil
	}
	state := &accumulator.capture.RawResponse
	if !capture {
		scanned := scanRawCaptureValue(raw, nil, nil, 0)
		accumulator.markRawResponseDroppedLocked(StreamCaptureReasonDisabled)
		state.ChunksSeen++
		state.DroppedBytes += scanned.bytes
		accumulator.recordRetentionEventLocked(StreamCapturePurposeRawResponse, *state)
		return nil
	}
	if state.Mode == "" {
		state.Mode = StreamCaptureModeFull
	}
	state.ChunksSeen++

	if state.Mode == StreamCaptureModeMetadataOnly || state.Mode == StreamCaptureModeDrop {
		scanned := scanRawCaptureValue(raw, state, &accumulator.rawDigest, 0)
		state.DroppedBytes += scanned.bytes
		accumulator.recordRetentionEventLocked(StreamCapturePurposeRawResponse, *state)
		return nil
	}
	if limit := a.options.Limits.RawResponseMaxDuration; limit > 0 && !accumulator.StartTimestamp.IsZero() && !timestamp.IsZero() && timestamp.Sub(accumulator.StartTimestamp) > limit {
		scanned := scanRawCaptureValue(raw, state, &accumulator.rawDigest, 0)
		state.Mode = StreamCaptureModeMetadataOnly
		state.Reason = StreamCaptureReasonTimeLimit
		state.DroppedBytes += state.RetainedBytes + scanned.bytes
		state.RetainedBytes = 0
		accumulator.clearRetainedRawResponsesLocked()
		accumulator.recordRetentionEventLocked(StreamCapturePurposeRawResponse, *state)
		return nil
	}
	bufferLimit := int64(-1)
	if limit := a.options.Limits.RawResponseMaxBytes; limit > 0 {
		bufferLimit = limit - state.RetainedBytes
		if bufferLimit < 0 {
			bufferLimit = 0
		}
	}
	scanned := scanRawCaptureValue(raw, state, &accumulator.rawDigest, bufferLimit)
	if limit := a.options.Limits.RawResponseMaxBytes; limit > 0 && state.RetainedBytes+scanned.bytes > limit {
		state.Mode = StreamCaptureModeMetadataOnly
		state.Reason = StreamCaptureReasonByteLimit
		state.DroppedBytes += state.RetainedBytes + scanned.bytes
		state.RetainedBytes = 0
		accumulator.clearRetainedRawResponsesLocked()
		accumulator.recordRetentionEventLocked(StreamCapturePurposeRawResponse, *state)
		return nil
	}

	state.RetainedBytes += scanned.bytes
	accumulator.recordRetentionEventLocked(StreamCapturePurposeRawResponse, *state)
	rawString := scanned.retained
	return &rawString
}

func (a *Accumulator) dropRawResponseForOutputDowngradeLocked(accumulator *StreamAccumulator, raw interface{}) {
	if raw == nil {
		return
	}
	state := &accumulator.capture.RawResponse
	if state.Mode == "" || state.Mode == StreamCaptureModeFull {
		state.Mode = StreamCaptureModeMetadataOnly
		state.Reason = StreamCaptureReasonOutputDowngrade
		state.DroppedBytes += state.RetainedBytes
		state.RetainedBytes = 0
		accumulator.clearRetainedRawResponsesLocked()
	}
	state.ChunksSeen++
	scanned := scanRawCaptureValue(raw, state, &accumulator.rawDigest, 0)
	state.DroppedBytes += scanned.bytes
	accumulator.recordRetentionEventLocked(StreamCapturePurposeRawResponse, *state)
}

func writeCaptureDigest(state *StreamCapturePurposeMetadata, digest *hash.Hash, b []byte) {
	if len(b) == 0 {
		return
	}
	if *digest == nil {
		*digest = sha256.New()
	}
	_, _ = (*digest).Write(b)
	state.DigestSHA256 = hex.EncodeToString((*digest).Sum(nil))
}

func writeCaptureDigestString(state *StreamCapturePurposeMetadata, digest *hash.Hash, s string) {
	if s == "" {
		return
	}
	if *digest == nil {
		*digest = sha256.New()
	}
	_, _ = io.WriteString(*digest, s)
	state.DigestSHA256 = hex.EncodeToString((*digest).Sum(nil))
}

func chatChunkPayloadBytes(chunk *ChatStreamChunk) int64 {
	return int64(len(chatChunkPayload(chunk)))
}

func chatChunkPayload(chunk *ChatStreamChunk) []byte {
	if chunk == nil || chunk.Delta == nil {
		return nil
	}
	return capturePayloadBytes(chunk.Delta)
}

func capturePayloadBytes(v interface{}) []byte {
	if v == nil {
		return nil
	}
	if b, err := schemas.MarshalSorted(v); err == nil {
		return b
	}
	return []byte(fmt.Sprintf("%v", v))
}

type outputLimit struct {
	maxBytes int64
	maxAge   time.Duration
}

func (a *Accumulator) outputLimitForStreamType(streamType StreamType) outputLimit {
	switch streamType {
	case StreamTypeChat, StreamTypeText:
		return outputLimit{maxBytes: a.options.Limits.ChatMaxRetainedBytes, maxAge: a.options.Limits.ChatMaxDuration}
	case StreamTypeResponses:
		return outputLimit{maxBytes: a.options.Limits.ResponsesMaxRetainedBytes, maxAge: a.options.Limits.ResponsesMaxDuration}
	case StreamTypeAudio:
		return outputLimit{maxBytes: a.options.Limits.AudioMaxRetainedBytes, maxAge: a.options.Limits.AudioMaxDuration}
	case StreamTypeTranscription:
		return outputLimit{maxBytes: a.options.Limits.TranscriptionMaxRetainedBytes, maxAge: a.options.Limits.TranscriptionMaxDuration}
	case StreamTypeImage:
		return outputLimit{maxBytes: a.options.Limits.ImageMaxRetainedBytes, maxAge: a.options.Limits.ImageMaxDuration}
	default:
		return outputLimit{}
	}
}

func copyChatMetadataOnly(chunk *ChatStreamChunk) *ChatStreamChunk {
	if chunk == nil {
		return nil
	}
	return &ChatStreamChunk{
		Timestamp:          chunk.Timestamp,
		FinishReason:       chunk.FinishReason,
		TokenUsage:         chunk.TokenUsage,
		SemanticCacheDebug: chunk.SemanticCacheDebug,
		Cost:               chunk.Cost,
		ErrorDetails:       chunk.ErrorDetails,
		ChunkIndex:         chunk.ChunkIndex,
	}
}

func (sa *StreamAccumulator) rememberChatMetadataLocked(chunk *ChatStreamChunk) {
	if chunk == nil {
		return
	}
	if chunk.ChunkIndex > sa.MaxChatChunkIndex {
		sa.MaxChatChunkIndex = chunk.ChunkIndex
	}
	if chunk.FinishReason != nil || chunk.TokenUsage != nil || chunk.SemanticCacheDebug != nil || chunk.Cost != nil || chunk.ErrorDetails != nil {
		if sa.metadataOnlyChatChunk == nil || chunk.ChunkIndex >= sa.metadataOnlyChatChunk.ChunkIndex {
			sa.metadataOnlyChatChunk = copyChatMetadataOnly(chunk)
		}
	}
}

func copyResponsesMetadataOnly(chunk *ResponsesStreamChunk) *ResponsesStreamChunk {
	if chunk == nil {
		return nil
	}
	return &ResponsesStreamChunk{
		Timestamp:          chunk.Timestamp,
		FinishReason:       chunk.FinishReason,
		TokenUsage:         chunk.TokenUsage,
		SemanticCacheDebug: chunk.SemanticCacheDebug,
		Cost:               chunk.Cost,
		ErrorDetails:       chunk.ErrorDetails,
		ChunkIndex:         chunk.ChunkIndex,
	}
}

func copyAudioMetadataOnly(chunk *AudioStreamChunk) *AudioStreamChunk {
	if chunk == nil {
		return nil
	}
	return &AudioStreamChunk{
		Timestamp:          chunk.Timestamp,
		FinishReason:       chunk.FinishReason,
		TokenUsage:         chunk.TokenUsage,
		SemanticCacheDebug: chunk.SemanticCacheDebug,
		Cost:               chunk.Cost,
		ErrorDetails:       chunk.ErrorDetails,
		ChunkIndex:         chunk.ChunkIndex,
	}
}

func copyTranscriptionMetadataOnly(chunk *TranscriptionStreamChunk) *TranscriptionStreamChunk {
	if chunk == nil {
		return nil
	}
	return &TranscriptionStreamChunk{
		Timestamp:          chunk.Timestamp,
		FinishReason:       chunk.FinishReason,
		TokenUsage:         chunk.TokenUsage,
		SemanticCacheDebug: chunk.SemanticCacheDebug,
		Cost:               chunk.Cost,
		ErrorDetails:       chunk.ErrorDetails,
		ChunkIndex:         chunk.ChunkIndex,
	}
}

func copyImageMetadataOnly(chunk *ImageStreamChunk) *ImageStreamChunk {
	if chunk == nil {
		return nil
	}
	return &ImageStreamChunk{
		Timestamp:          chunk.Timestamp,
		FinishReason:       chunk.FinishReason,
		TokenUsage:         chunk.TokenUsage,
		SemanticCacheDebug: chunk.SemanticCacheDebug,
		Cost:               chunk.Cost,
		ErrorDetails:       chunk.ErrorDetails,
		ChunkIndex:         chunk.ChunkIndex,
		ImageIndex:         chunk.ImageIndex,
	}
}

func (sa *StreamAccumulator) rememberResponsesMetadataLocked(chunk *ResponsesStreamChunk) {
	if chunk == nil {
		return
	}
	if chunk.ChunkIndex > sa.MaxResponsesChunkIndex {
		sa.MaxResponsesChunkIndex = chunk.ChunkIndex
	}
	if chunk.FinishReason != nil || chunk.TokenUsage != nil || chunk.SemanticCacheDebug != nil || chunk.Cost != nil || chunk.ErrorDetails != nil {
		if sa.metadataOnlyResponsesChunk == nil || chunk.ChunkIndex >= sa.metadataOnlyResponsesChunk.ChunkIndex {
			sa.metadataOnlyResponsesChunk = copyResponsesMetadataOnly(chunk)
		}
	}
}

func (sa *StreamAccumulator) rememberAudioMetadataLocked(chunk *AudioStreamChunk) {
	if chunk == nil {
		return
	}
	if chunk.ChunkIndex > sa.MaxAudioChunkIndex {
		sa.MaxAudioChunkIndex = chunk.ChunkIndex
	}
	if chunk.FinishReason != nil || chunk.TokenUsage != nil || chunk.SemanticCacheDebug != nil || chunk.Cost != nil || chunk.ErrorDetails != nil {
		if sa.metadataOnlyAudioChunk == nil || chunk.ChunkIndex >= sa.metadataOnlyAudioChunk.ChunkIndex {
			sa.metadataOnlyAudioChunk = copyAudioMetadataOnly(chunk)
		}
	}
}

func (sa *StreamAccumulator) rememberTranscriptionMetadataLocked(chunk *TranscriptionStreamChunk) {
	if chunk == nil {
		return
	}
	if chunk.ChunkIndex > sa.MaxTranscriptionChunkIndex {
		sa.MaxTranscriptionChunkIndex = chunk.ChunkIndex
	}
	if chunk.FinishReason != nil || chunk.TokenUsage != nil || chunk.SemanticCacheDebug != nil || chunk.Cost != nil || chunk.ErrorDetails != nil {
		if sa.metadataOnlyTranscriptionChunk == nil || chunk.ChunkIndex >= sa.metadataOnlyTranscriptionChunk.ChunkIndex {
			sa.metadataOnlyTranscriptionChunk = copyTranscriptionMetadataOnly(chunk)
		}
	}
}

func (sa *StreamAccumulator) rememberImageMetadataLocked(chunk *ImageStreamChunk) {
	if chunk == nil {
		return
	}
	if chunk.FinishReason != nil || chunk.TokenUsage != nil || chunk.SemanticCacheDebug != nil || chunk.Cost != nil || chunk.ErrorDetails != nil {
		if sa.metadataOnlyImageChunk == nil || chunk.ChunkIndex >= sa.metadataOnlyImageChunk.ChunkIndex {
			sa.metadataOnlyImageChunk = copyImageMetadataOnly(chunk)
		}
	}
}

func rememberMetadataSeenInt(seen map[int]struct{}, key int) {
	if seen == nil {
		return
	}
	if len(seen) >= metadataDedupeMaxEntries {
		for k := range seen {
			delete(seen, k)
			if len(seen) <= metadataDedupeMaxEntries/2 {
				break
			}
		}
	}
	seen[key] = struct{}{}
}

func rememberMetadataSeenString(seen map[string]struct{}, key string) {
	if seen == nil {
		return
	}
	if len(seen) >= metadataDedupeMaxEntries {
		for k := range seen {
			delete(seen, k)
			if len(seen) <= metadataDedupeMaxEntries/2 {
				break
			}
		}
	}
	seen[key] = struct{}{}
}

func (a *Accumulator) downgradeOutputLocked(sa *StreamAccumulator, streamType StreamType, reason string) {
	state := &sa.capture.Output
	if state.Mode == StreamCaptureModeMetadataOnly {
		return
	}
	state.Mode = StreamCaptureModeMetadataOnly
	state.Reason = reason
	state.DroppedBytes += state.RetainedBytes
	state.RetainedBytes = 0
	switch streamType {
	case StreamTypeChat, StreamTypeText:
		for _, chunk := range sa.ChatStreamChunks {
			a.putChatStreamChunk(chunk)
		}
		sa.ChatStreamChunks = nil
		sa.ChatChunksSeen = make(map[int]struct{})
	case StreamTypeResponses:
		for _, chunk := range sa.ResponsesStreamChunks {
			a.putResponsesStreamChunk(chunk)
		}
		sa.ResponsesStreamChunks = nil
		sa.ResponsesChunksSeen = make(map[int]struct{})
	case StreamTypeAudio:
		for _, chunk := range sa.AudioStreamChunks {
			a.putAudioStreamChunk(chunk)
		}
		sa.AudioStreamChunks = nil
		sa.AudioChunksSeen = make(map[int]struct{})
	case StreamTypeTranscription:
		for _, chunk := range sa.TranscriptionStreamChunks {
			a.putTranscriptionStreamChunk(chunk)
		}
		sa.TranscriptionStreamChunks = nil
		sa.TranscriptionChunksSeen = make(map[int]struct{})
	case StreamTypeImage:
		for _, chunk := range sa.ImageStreamChunks {
			a.putImageStreamChunk(chunk)
		}
		sa.ImageStreamChunks = nil
		sa.ImageChunksSeen = make(map[string]struct{})
	}
}

func (a *Accumulator) shouldRetainOutputPayloadLocked(sa *StreamAccumulator, streamType StreamType, payload []byte, timestamp time.Time, rememberMetadata func()) bool {
	state := &sa.capture.Output
	if state.Mode == "" {
		state.Mode = StreamCaptureModeFull
	}
	payloadBytes := int64(len(payload))
	state.ChunksSeen++
	writeCaptureDigest(state, &sa.outputDigest, payload)

	if state.Mode == StreamCaptureModeMetadataOnly || state.Mode == StreamCaptureModeDrop {
		state.DroppedBytes += payloadBytes
		rememberMetadata()
		sa.recordRetentionEventLocked(StreamCapturePurposeOutput, *state)
		return false
	}

	limit := a.outputLimitForStreamType(streamType)
	if limit.maxAge > 0 && !sa.StartTimestamp.IsZero() && !timestamp.IsZero() && timestamp.Sub(sa.StartTimestamp) > limit.maxAge {
		a.downgradeOutputLocked(sa, streamType, StreamCaptureReasonTimeLimit)
		state.DroppedBytes += payloadBytes
		rememberMetadata()
		sa.recordRetentionEventLocked(StreamCapturePurposeOutput, *state)
		return false
	}

	if limit.maxBytes > 0 && state.RetainedBytes+payloadBytes > limit.maxBytes {
		a.downgradeOutputLocked(sa, streamType, StreamCaptureReasonByteLimit)
		state.DroppedBytes += payloadBytes
		rememberMetadata()
		sa.recordRetentionEventLocked(StreamCapturePurposeOutput, *state)
		return false
	}

	state.RetainedBytes += payloadBytes
	sa.recordRetentionEventLocked(StreamCapturePurposeOutput, *state)
	return true
}

func (a *Accumulator) shouldRetainChatChunkLocked(sa *StreamAccumulator, chunk *ChatStreamChunk, streamType StreamType) bool {
	return a.shouldRetainOutputPayloadLocked(sa, streamType, chatChunkPayload(chunk), chunk.Timestamp, func() {
		sa.rememberChatMetadataLocked(chunk)
	})
}

func (a *Accumulator) captureChunkRawResponseLocked(sa *StreamAccumulator, retained bool, raw interface{}, capture bool, timestamp time.Time) *string {
	if raw == nil {
		return nil
	}
	if !retained {
		if !capture {
			return a.captureRawResponseLocked(sa, false, raw, timestamp)
		}
		a.dropRawResponseForOutputDowngradeLocked(sa, raw)
		return nil
	}
	return a.captureRawResponseLocked(sa, capture, raw, timestamp)
}

func (a *Accumulator) retainPassthroughBodyLocked(sa *StreamAccumulator, body []byte, timestamp time.Time) []byte {
	if len(body) == 0 {
		return nil
	}
	state := &sa.capture.PassthroughBody
	if state.Mode == "" {
		state.Mode = StreamCaptureModeFull
	}
	bodyBytes := int64(len(body))
	state.ChunksSeen++
	writeCaptureDigest(state, &sa.passthroughDigest, body)

	if state.Mode == StreamCaptureModeMetadataOnly || state.Mode == StreamCaptureModeDrop {
		state.DroppedBytes += bodyBytes
		sa.recordRetentionEventLocked(StreamCapturePurposePassthroughBody, *state)
		return nil
	}
	if limit := a.options.Limits.PassthroughMaxDuration; limit > 0 && !sa.StartTimestamp.IsZero() && !timestamp.IsZero() && timestamp.Sub(sa.StartTimestamp) > limit {
		state.Mode = StreamCaptureModeMetadataOnly
		state.Reason = StreamCaptureReasonTimeLimit
		state.DroppedBytes += state.RetainedBytes + bodyBytes
		state.RetainedBytes = 0
		sa.PassthroughBody = nil
		sa.recordRetentionEventLocked(StreamCapturePurposePassthroughBody, *state)
		return nil
	}
	if limit := a.options.Limits.PassthroughMaxRetainedBytes; limit > 0 && state.RetainedBytes+bodyBytes > limit {
		state.Mode = StreamCaptureModeMetadataOnly
		state.Reason = StreamCaptureReasonByteLimit
		state.DroppedBytes += state.RetainedBytes + bodyBytes
		state.RetainedBytes = 0
		sa.PassthroughBody = nil
		sa.recordRetentionEventLocked(StreamCapturePurposePassthroughBody, *state)
		return nil
	}

	bodyCopy := make([]byte, len(body))
	copy(bodyCopy, body)
	state.RetainedBytes += bodyBytes
	sa.recordRetentionEventLocked(StreamCapturePurposePassthroughBody, *state)
	return bodyCopy
}

func retainedPassthroughHeaderBytes(headers map[string]string) int64 {
	var total int64
	for name, value := range headers {
		total += int64(len(name) + len(value))
	}
	return total
}

func (a *Accumulator) retainPassthroughHeadersLocked(sa *StreamAccumulator, headers map[string]string) {
	if len(headers) == 0 {
		return
	}
	if sa.PassthroughHeaders == nil {
		sa.PassthroughHeaders = make(map[string]string)
	}
	state := &sa.capture.PassthroughHeaders
	if state.Mode == "" {
		state.Mode = StreamCaptureModeFull
	}
	limits := a.options.Limits

	for name, value := range headers {
		headerBytes := int64(len(name) + len(value))
		state.ChunksSeen++
		writeCaptureDigestString(state, &sa.passthroughHeaderDigest, name)
		writeCaptureDigestString(state, &sa.passthroughHeaderDigest, "\x00")
		writeCaptureDigestString(state, &sa.passthroughHeaderDigest, value)
		writeCaptureDigestString(state, &sa.passthroughHeaderDigest, "\x00")

		if state.Mode == StreamCaptureModeMetadataOnly || state.Mode == StreamCaptureModeDrop {
			state.DroppedBytes += headerBytes
			continue
		}

		if limits.PassthroughMaxHeaderNameBytes > 0 && len(name) > limits.PassthroughMaxHeaderNameBytes {
			state.Mode = StreamCaptureModeMetadataOnly
			state.Reason = StreamCaptureReasonByteLimit
			state.DroppedBytes += headerBytes
			continue
		}
		if limits.PassthroughMaxHeaderValueBytes > 0 && len(value) > limits.PassthroughMaxHeaderValueBytes {
			state.Mode = StreamCaptureModeMetadataOnly
			state.Reason = StreamCaptureReasonByteLimit
			state.DroppedBytes += headerBytes
			continue
		}

		existingValue, exists := sa.PassthroughHeaders[name]
		projectedCount := len(sa.PassthroughHeaders)
		if !exists {
			projectedCount++
		}
		if limits.PassthroughMaxHeaderCount > 0 && projectedCount > limits.PassthroughMaxHeaderCount {
			state.Mode = StreamCaptureModeMetadataOnly
			state.Reason = StreamCaptureReasonByteLimit
			state.DroppedBytes += headerBytes
			continue
		}

		projectedBytes := retainedPassthroughHeaderBytes(sa.PassthroughHeaders)
		if exists {
			projectedBytes -= int64(len(name) + len(existingValue))
		}
		projectedBytes += headerBytes
		if limits.PassthroughMaxHeaderTotalBytes > 0 && projectedBytes > limits.PassthroughMaxHeaderTotalBytes {
			state.Mode = StreamCaptureModeMetadataOnly
			state.Reason = StreamCaptureReasonByteLimit
			state.DroppedBytes += headerBytes
			continue
		}

		sa.PassthroughHeaders[name] = value
		state.RetainedBytes = projectedBytes
	}
	state.RetainedBytes = retainedPassthroughHeaderBytes(sa.PassthroughHeaders)
	sa.recordRetentionEventLocked(StreamCapturePurposePassthroughHeaders, *state)
}

func (sa *StreamAccumulator) captureSnapshotLocked() *StreamCaptureMetadata {
	capture := sa.capture
	if capture.Output.Mode == "" {
		capture.Output.Mode = StreamCaptureModeFull
	}
	if capture.RawResponse.Mode == "" {
		capture.RawResponse.Mode = StreamCaptureModeFull
	}
	if capture.PassthroughBody.Mode == "" {
		capture.PassthroughBody.Mode = StreamCaptureModeFull
	}
	if capture.PassthroughHeaders.Mode == "" {
		capture.PassthroughHeaders.Mode = StreamCaptureModeFull
	}
	return &capture
}

// getOrCreateStreamAccumulator gets or creates a stream accumulator for a request
func (a *Accumulator) getOrCreateStreamAccumulator(requestID string) *StreamAccumulator {
	// Fast path: check if already exists (no allocation)
	if acc, exists := a.streamAccumulators.Load(requestID); exists {
		return acc.(*StreamAccumulator)
	}

	// Slow path: create new accumulator
	now := time.Now()
	newAcc := &StreamAccumulator{
		RequestID:                  requestID,
		ChatStreamChunks:           make([]*ChatStreamChunk, 0),
		ResponsesStreamChunks:      make([]*ResponsesStreamChunk, 0),
		ImageStreamChunks:          make([]*ImageStreamChunk, 0),
		TranscriptionStreamChunks:  make([]*TranscriptionStreamChunk, 0),
		AudioStreamChunks:          make([]*AudioStreamChunk, 0),
		ChatChunksSeen:             make(map[int]struct{}),
		ResponsesChunksSeen:        make(map[int]struct{}),
		TranscriptionChunksSeen:    make(map[int]struct{}),
		AudioChunksSeen:            make(map[int]struct{}),
		ImageChunksSeen:            make(map[string]struct{}),
		MaxChatChunkIndex:          -1,
		MaxResponsesChunkIndex:     -1,
		MaxTranscriptionChunkIndex: -1,
		MaxAudioChunkIndex:         -1,
		TerminalErrorChunkIndex:    -1,
		TerminalResponseChunkIndex: -1,
		IsComplete:                 false,
		mu:                         sync.Mutex{},
		Timestamp:                  now,
		StartTimestamp:             now,
		gateState:                  StreamStateActive,
		gatePausedAt:               -1,
		cancelWatchDone:            make(chan struct{}),
		parent:                     a,
	}
	newAcc.gateCond = sync.NewCond(&newAcc.mu)

	// LoadOrStore atomically: if key exists, return existing; else store new
	actual, _ := a.streamAccumulators.LoadOrStore(requestID, newAcc)
	return actual.(*StreamAccumulator)
}

// WatchContextCancellation arranges for a live stream accumulator to be reaped
// when its request context is canceled, even if no later chunk arrives.
func (a *Accumulator) WatchContextCancellation(requestID string, ctx context.Context) {
	if a == nil || requestID == "" || ctx == nil || ctx.Done() == nil {
		return
	}
	acc := a.getOrCreateStreamAccumulator(requestID)
	acc.cancelWatchOnce.Do(func() {
		done := acc.cancelWatchDone
		go func() {
			select {
			case <-ctx.Done():
				a.ForceCleanupStreamAccumulator(requestID)
			case <-done:
			case <-a.stopCleanup:
			}
		}()
	})
}

// addChatStreamChunk adds a chat or text-completion chunk to the stream accumulator.
// Both stream kinds share ChatStreamChunks, so the stream type is retained separately
// to build the correct response shape for on-demand snapshots.
func (a *Accumulator) addChatStreamChunk(requestID string, streamType StreamType, chunk *ChatStreamChunk, isFinalChunk bool) error {
	if streamType != StreamTypeChat && streamType != StreamTypeText {
		a.putChatStreamChunk(chunk)
		return fmt.Errorf("invalid chat stream type %q", streamType)
	}

	accumulator := a.getOrCreateStreamAccumulator(requestID)
	// Lock the accumulator
	accumulator.mu.Lock()
	defer accumulator.mu.Unlock()
	if accumulator.chatStreamType == "" {
		accumulator.chatStreamType = streamType
	} else if accumulator.chatStreamType != streamType {
		a.putChatStreamChunk(chunk)
		return fmt.Errorf("inconsistent chat stream type for request %s: got %q after %q", requestID, streamType, accumulator.chatStreamType)
	}
	if accumulator.StartTimestamp.IsZero() {
		accumulator.StartTimestamp = chunk.Timestamp
	}
	// Track first chunk timestamp for TTFT calculation
	if accumulator.FirstChunkTimestamp.IsZero() {
		accumulator.FirstChunkTimestamp = chunk.Timestamp
	}
	// De-dup check - only add if not seen (handles out-of-order arrival and multiple plugins)
	if accumulator.capture.Output.Mode == StreamCaptureModeMetadataOnly || accumulator.capture.Output.Mode == StreamCaptureModeDrop {
		if _, seen := accumulator.ChatChunksSeen[chunk.ChunkIndex]; seen {
			a.putChatStreamChunk(chunk)
			if isFinalChunk {
				accumulator.FinalTimestamp = chunk.Timestamp
			}
			return nil
		}
		rememberMetadataSeenInt(accumulator.ChatChunksSeen, chunk.ChunkIndex)
		retained := a.shouldRetainChatChunkLocked(accumulator, chunk, streamType)
		chunk.RawResponse = a.captureChunkRawResponseLocked(accumulator, retained, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
		a.putChatStreamChunk(chunk)
	} else if _, seen := accumulator.ChatChunksSeen[chunk.ChunkIndex]; !seen {
		if !a.shouldRetainChatChunkLocked(accumulator, chunk, streamType) {
			rememberMetadataSeenInt(accumulator.ChatChunksSeen, chunk.ChunkIndex)
			_ = a.captureChunkRawResponseLocked(accumulator, false, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
			a.putChatStreamChunk(chunk)
			if isFinalChunk {
				accumulator.FinalTimestamp = chunk.Timestamp
			}
			return nil
		}
		chunk.RawResponse = a.captureChunkRawResponseLocked(accumulator, true, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
		accumulator.ChatChunksSeen[chunk.ChunkIndex] = struct{}{}
		accumulator.ChatStreamChunks = append(accumulator.ChatStreamChunks, chunk)
		// Track max index for metadata extraction
		if chunk.ChunkIndex > accumulator.MaxChatChunkIndex {
			accumulator.MaxChatChunkIndex = chunk.ChunkIndex
		}
	} else {
		a.putChatStreamChunk(chunk)
	}
	// Check if this is the final chunk
	// Set FinalTimestamp when either FinishReason is present or token usage exists
	// This handles both normal completion chunks and usage-only last chunks
	if isFinalChunk {
		accumulator.FinalTimestamp = chunk.Timestamp
	}
	return nil
}

// AddTranscriptionStreamChunk adds a transcription stream chunk to the stream accumulator
func (a *Accumulator) addTranscriptionStreamChunk(requestID string, chunk *TranscriptionStreamChunk, isFinalChunk bool) error {
	accumulator := a.getOrCreateStreamAccumulator(requestID)
	// Lock the accumulator
	accumulator.mu.Lock()
	defer accumulator.mu.Unlock()
	if accumulator.StartTimestamp.IsZero() {
		accumulator.StartTimestamp = chunk.Timestamp
	}
	// Track first chunk timestamp for TTFT calculation
	if accumulator.FirstChunkTimestamp.IsZero() {
		accumulator.FirstChunkTimestamp = chunk.Timestamp
	}
	if accumulator.capture.Output.Mode == StreamCaptureModeMetadataOnly || accumulator.capture.Output.Mode == StreamCaptureModeDrop {
		if _, seen := accumulator.TranscriptionChunksSeen[chunk.ChunkIndex]; seen {
			a.putTranscriptionStreamChunk(chunk)
			if isFinalChunk {
				accumulator.FinalTimestamp = chunk.Timestamp
			}
			return nil
		}
		rememberMetadataSeenInt(accumulator.TranscriptionChunksSeen, chunk.ChunkIndex)
		retained := a.shouldRetainOutputPayloadLocked(accumulator, StreamTypeTranscription, capturePayloadBytes(chunk.Delta), chunk.Timestamp, func() {
			accumulator.rememberTranscriptionMetadataLocked(chunk)
		})
		chunk.RawResponse = a.captureChunkRawResponseLocked(accumulator, retained, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
		a.putTranscriptionStreamChunk(chunk)
	} else if _, seen := accumulator.TranscriptionChunksSeen[chunk.ChunkIndex]; !seen {
		if !a.shouldRetainOutputPayloadLocked(accumulator, StreamTypeTranscription, capturePayloadBytes(chunk.Delta), chunk.Timestamp, func() {
			accumulator.rememberTranscriptionMetadataLocked(chunk)
		}) {
			rememberMetadataSeenInt(accumulator.TranscriptionChunksSeen, chunk.ChunkIndex)
			_ = a.captureChunkRawResponseLocked(accumulator, false, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
			a.putTranscriptionStreamChunk(chunk)
			if isFinalChunk {
				accumulator.FinalTimestamp = chunk.Timestamp
			}
			return nil
		}
		chunk.RawResponse = a.captureChunkRawResponseLocked(accumulator, true, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
		accumulator.TranscriptionChunksSeen[chunk.ChunkIndex] = struct{}{}
		accumulator.TranscriptionStreamChunks = append(accumulator.TranscriptionStreamChunks, chunk)
		// Track max index for metadata extraction
		if chunk.ChunkIndex > accumulator.MaxTranscriptionChunkIndex {
			accumulator.MaxTranscriptionChunkIndex = chunk.ChunkIndex
		}
	} else {
		a.putTranscriptionStreamChunk(chunk)
	}
	// Check if this is the final chunk
	// Set FinalTimestamp when either FinishReason is present or token usage exists
	// This handles both normal completion chunks and usage-only last chunks
	if isFinalChunk {
		accumulator.FinalTimestamp = chunk.Timestamp
	}
	return nil
}

// addAudioStreamChunk adds an audio stream chunk to the stream accumulator
func (a *Accumulator) addAudioStreamChunk(requestID string, chunk *AudioStreamChunk, isFinalChunk bool) error {
	accumulator := a.getOrCreateStreamAccumulator(requestID)
	// Lock the accumulator
	accumulator.mu.Lock()
	defer accumulator.mu.Unlock()
	if accumulator.StartTimestamp.IsZero() {
		accumulator.StartTimestamp = chunk.Timestamp
	}
	// Track first chunk timestamp for TTFT calculation
	if accumulator.FirstChunkTimestamp.IsZero() {
		accumulator.FirstChunkTimestamp = chunk.Timestamp
	}
	if accumulator.capture.Output.Mode == StreamCaptureModeMetadataOnly || accumulator.capture.Output.Mode == StreamCaptureModeDrop {
		if _, seen := accumulator.AudioChunksSeen[chunk.ChunkIndex]; seen {
			a.putAudioStreamChunk(chunk)
			if isFinalChunk {
				accumulator.FinalTimestamp = chunk.Timestamp
			}
			return nil
		}
		rememberMetadataSeenInt(accumulator.AudioChunksSeen, chunk.ChunkIndex)
		retained := a.shouldRetainOutputPayloadLocked(accumulator, StreamTypeAudio, capturePayloadBytes(chunk.Delta), chunk.Timestamp, func() {
			accumulator.rememberAudioMetadataLocked(chunk)
		})
		chunk.RawResponse = a.captureChunkRawResponseLocked(accumulator, retained, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
		a.putAudioStreamChunk(chunk)
	} else if _, seen := accumulator.AudioChunksSeen[chunk.ChunkIndex]; !seen {
		if !a.shouldRetainOutputPayloadLocked(accumulator, StreamTypeAudio, capturePayloadBytes(chunk.Delta), chunk.Timestamp, func() {
			accumulator.rememberAudioMetadataLocked(chunk)
		}) {
			rememberMetadataSeenInt(accumulator.AudioChunksSeen, chunk.ChunkIndex)
			_ = a.captureChunkRawResponseLocked(accumulator, false, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
			a.putAudioStreamChunk(chunk)
			if isFinalChunk {
				accumulator.FinalTimestamp = chunk.Timestamp
			}
			return nil
		}
		chunk.RawResponse = a.captureChunkRawResponseLocked(accumulator, true, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
		accumulator.AudioChunksSeen[chunk.ChunkIndex] = struct{}{}
		accumulator.AudioStreamChunks = append(accumulator.AudioStreamChunks, chunk)
		// Track max index for metadata extraction
		if chunk.ChunkIndex > accumulator.MaxAudioChunkIndex {
			accumulator.MaxAudioChunkIndex = chunk.ChunkIndex
		}
	} else {
		a.putAudioStreamChunk(chunk)
	}
	// Check if this is the final chunk
	// Set FinalTimestamp when either FinishReason is present or token usage exists
	// This handles both normal completion chunks and usage-only last chunks
	if isFinalChunk {
		accumulator.FinalTimestamp = chunk.Timestamp
	}
	return nil
}

// reserveTerminalChunkIndex returns the stable chunk index reserved for a terminal
// chunk, seeding the reservation on first call: an index that is already unique
// (greater than the current max) is reserved as-is, while a reused/lower one gets a
// fresh trailing index. Duplicate plugin deliveries of the same terminal chunk then
// remap to the reservation and are dropped by the seen-index dedup. Keep separate
// reservation fields per terminal kind (error vs response) — merging them would
// change dedup behavior if a stream ever produced both. Caller must hold mu.
func (sa *StreamAccumulator) reserveTerminalChunkIndex(field *int, chunkIndex int) int {
	if *field >= 0 {
		return *field
	}
	if chunkIndex <= sa.MaxResponsesChunkIndex {
		sa.MaxResponsesChunkIndex++
		chunkIndex = sa.MaxResponsesChunkIndex
	}
	*field = chunkIndex
	return chunkIndex
}

// addResponsesStreamChunk adds a responses stream chunk to the stream accumulator
func (a *Accumulator) addResponsesStreamChunk(requestID string, chunk *ResponsesStreamChunk, isFinalChunk bool) error {
	accumulator := a.getOrCreateStreamAccumulator(requestID)
	// Lock the accumulator
	accumulator.mu.Lock()
	defer accumulator.mu.Unlock()
	if accumulator.StartTimestamp.IsZero() {
		accumulator.StartTimestamp = chunk.Timestamp
	}
	// Track first chunk timestamp for TTFT calculation
	if accumulator.FirstChunkTimestamp.IsZero() {
		accumulator.FirstChunkTimestamp = chunk.Timestamp
	}
	if isFinalChunk && chunk.StreamResponse != nil {
		chunk.ChunkIndex = accumulator.reserveTerminalChunkIndex(&accumulator.TerminalResponseChunkIndex, chunk.ChunkIndex)
	}
	if accumulator.capture.Output.Mode == StreamCaptureModeMetadataOnly || accumulator.capture.Output.Mode == StreamCaptureModeDrop {
		if _, seen := accumulator.ResponsesChunksSeen[chunk.ChunkIndex]; seen {
			a.putResponsesStreamChunk(chunk)
			if isFinalChunk {
				accumulator.FinalTimestamp = chunk.Timestamp
			}
			return nil
		}
		rememberMetadataSeenInt(accumulator.ResponsesChunksSeen, chunk.ChunkIndex)
		retained := a.shouldRetainOutputPayloadLocked(accumulator, StreamTypeResponses, capturePayloadBytes(chunk.StreamResponse), chunk.Timestamp, func() {
			accumulator.rememberResponsesMetadataLocked(chunk)
		})
		chunk.RawResponse = a.captureChunkRawResponseLocked(accumulator, retained, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
		a.putResponsesStreamChunk(chunk)
	} else if _, seen := accumulator.ResponsesChunksSeen[chunk.ChunkIndex]; !seen {
		if !a.shouldRetainOutputPayloadLocked(accumulator, StreamTypeResponses, capturePayloadBytes(chunk.StreamResponse), chunk.Timestamp, func() {
			accumulator.rememberResponsesMetadataLocked(chunk)
		}) {
			rememberMetadataSeenInt(accumulator.ResponsesChunksSeen, chunk.ChunkIndex)
			_ = a.captureChunkRawResponseLocked(accumulator, false, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
			a.putResponsesStreamChunk(chunk)
			if isFinalChunk {
				accumulator.FinalTimestamp = chunk.Timestamp
			}
			return nil
		}
		chunk.RawResponse = a.captureChunkRawResponseLocked(accumulator, true, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
		accumulator.ResponsesChunksSeen[chunk.ChunkIndex] = struct{}{}
		accumulator.ResponsesStreamChunks = append(accumulator.ResponsesStreamChunks, chunk)
		// Track max index for metadata extraction
		if chunk.ChunkIndex > accumulator.MaxResponsesChunkIndex {
			accumulator.MaxResponsesChunkIndex = chunk.ChunkIndex
		}
	} else {
		a.putResponsesStreamChunk(chunk)
	}
	// Check if this is the final chunk
	// Set FinalTimestamp when either FinishReason is present or token usage exists
	// This handles both normal completion chunks and usage-only last chunks
	if isFinalChunk {
		accumulator.FinalTimestamp = chunk.Timestamp
	}
	return nil
}

// imageChunkKey creates a composite key for image chunk de-duplication
func imageChunkKey(imageIndex, chunkIndex int) string {
	return fmt.Sprintf("%d:%d", imageIndex, chunkIndex)
}

// addImageStreamChunk adds an image stream chunk to the stream accumulator
func (a *Accumulator) addImageStreamChunk(requestID string, chunk *ImageStreamChunk, isFinalChunk bool) error {
	acc := a.getOrCreateStreamAccumulator(requestID)
	acc.mu.Lock()
	defer acc.mu.Unlock()

	if acc.StartTimestamp.IsZero() {
		acc.StartTimestamp = chunk.Timestamp
	}
	if acc.FirstChunkTimestamp.IsZero() {
		acc.FirstChunkTimestamp = chunk.Timestamp
	}

	// De-dup check - only add if not seen (handles out-of-order arrival and multiple plugins)
	chunkKey := imageChunkKey(chunk.ImageIndex, chunk.ChunkIndex)
	if acc.capture.Output.Mode == StreamCaptureModeMetadataOnly || acc.capture.Output.Mode == StreamCaptureModeDrop {
		if _, seen := acc.ImageChunksSeen[chunkKey]; seen {
			a.putImageStreamChunk(chunk)
			if isFinalChunk {
				acc.FinalTimestamp = chunk.Timestamp
			}
			return nil
		}
		rememberMetadataSeenString(acc.ImageChunksSeen, chunkKey)
		retained := a.shouldRetainOutputPayloadLocked(acc, StreamTypeImage, capturePayloadBytes(chunk.Delta), chunk.Timestamp, func() {
			acc.rememberImageMetadataLocked(chunk)
		})
		chunk.RawResponse = a.captureChunkRawResponseLocked(acc, retained, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
		a.putImageStreamChunk(chunk)
	} else if _, seen := acc.ImageChunksSeen[chunkKey]; !seen {
		if !a.shouldRetainOutputPayloadLocked(acc, StreamTypeImage, capturePayloadBytes(chunk.Delta), chunk.Timestamp, func() {
			acc.rememberImageMetadataLocked(chunk)
		}) {
			rememberMetadataSeenString(acc.ImageChunksSeen, chunkKey)
			_ = a.captureChunkRawResponseLocked(acc, false, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
			a.putImageStreamChunk(chunk)
			if isFinalChunk {
				acc.FinalTimestamp = chunk.Timestamp
			}
			return nil
		}
		chunk.RawResponse = a.captureChunkRawResponseLocked(acc, true, chunk.rawResponseCandidate, chunk.captureRawResponse, chunk.Timestamp)
		acc.ImageChunksSeen[chunkKey] = struct{}{}
		acc.ImageStreamChunks = append(acc.ImageStreamChunks, chunk)
	} else {
		a.putImageStreamChunk(chunk)
	}
	// Check if this is the final chunk
	// Set FinalTimestamp when this is the final chunk, regardless of de-dup status
	// This handles cases where final chunk arrives after duplicates or is itself duplicated
	if isFinalChunk {
		acc.FinalTimestamp = chunk.Timestamp
	}
	return nil
}

// cleanupStreamAccumulator removes the stream accumulator for a request.
// IMPORTANT: Caller must hold accumulator.mu lock before calling this function
// to prevent races when returning chunks to pools.
//
// forceEndGate=true is for orphan/TTL cleanup paths where the flusher may be
// stuck in cond.Wait and must be woken by force-ending. forceEndGate=false is
// for natural-completion cleanup (refcount-driven from plugins): if the gate
// is still busy (flusher running OR Paused), teardown is deferred — the
// gatePendingCleanup flag is set, and the flusher's exit defer re-runs this
// cleanup once it's safe.
func (a *Accumulator) cleanupStreamAccumulator(requestID string, forceEndGate bool) {
	accumulator, exists := a.streamAccumulators.Load(requestID)
	if !exists {
		return
	}
	acc := accumulator.(*StreamAccumulator)

	// Defer teardown if the gate is still working and the caller didn't ask
	// for a forcible reap. The flusher's exit will pick this up.
	if !forceEndGate && (acc.gateFlusherOn || acc.gateState == StreamStatePaused) {
		acc.gatePendingCleanup = true
		return
	}

	if acc.cancelWatchDone != nil {
		acc.cancelWatchStopOnce.Do(func() {
			close(acc.cancelWatchDone)
		})
	}

	// Orphan path: force the gate to terminate so any blocked flusher wakes
	// up and exits. Drops buffered chunks — acceptable because the consumer
	// of an orphaned stream is gone by definition.
	if forceEndGate && acc.gateState != StreamStateEnded {
		acc.gateState = StreamStateEnded
		// Force-end is drop-only: clear any staged terminal-error delivery so
		// a flusher woken by the broadcast below cannot reach the
		// sendOrCancel(errChunk) path on an abandoned consumer channel.
		acc.gatePendingTerminal = false
		acc.gateEndError = nil
		if acc.gateCond != nil {
			acc.gateCond.Broadcast()
		}
		acc.gateReplayBuf = nil
		acc.gateReplayBufBytes = 0
	}

	// Return all chunks to the pool before deleting
	for _, chunk := range acc.ChatStreamChunks {
		a.putChatStreamChunk(chunk)
	}
	for _, chunk := range acc.ResponsesStreamChunks {
		a.putResponsesStreamChunk(chunk)
	}
	for _, chunk := range acc.AudioStreamChunks {
		a.putAudioStreamChunk(chunk)
	}
	for _, chunk := range acc.TranscriptionStreamChunks {
		a.putTranscriptionStreamChunk(chunk)
	}
	for _, chunk := range acc.ImageStreamChunks {
		a.putImageStreamChunk(chunk)
	}
	a.streamAccumulators.Delete(requestID)
	if forceEndGate {
		a.endedStreamIDs.Store(requestID, time.Now())
	}
}

// ProcessStreamingResponse processes a streaming response
// It handles chat, audio, and responses streaming responses
func (a *Accumulator) ProcessStreamingResponse(ctx *schemas.BifrostContext, result *schemas.BifrostResponse, bifrostErr *schemas.BifrostError) (*ProcessedStreamResponse, error) {
	var requestID string
	if ctx != nil {
		requestID, _ = getAccumulatorID(ctx)
		defer a.flushRetentionEvents(requestID)
		if err := ctx.Err(); err != nil {
			if requestID != "" {
				a.ForceCleanupStreamAccumulator(requestID)
			}
			return nil, err
		}
	}
	// Check if at least one of result or error is provided
	if result == nil && bifrostErr == nil {
		return nil, fmt.Errorf("result and error are nil")
	}

	var requestType schemas.RequestType
	if result != nil {
		requestType = result.GetExtraFields().RequestType
	} else if bifrostErr != nil {
		requestType = bifrostErr.ExtraFields.RequestType
	}

	isAudioStreaming := requestType == schemas.SpeechStreamRequest || requestType == schemas.TranscriptionStreamRequest
	isChatStreaming := requestType == schemas.ChatCompletionStreamRequest || requestType == schemas.TextCompletionStreamRequest
	isResponsesStreaming := requestType == schemas.ResponsesStreamRequest || requestType == schemas.WebSocketResponsesRequest
	// Edit images/ Image variation requests will be added here
	isImageStreaming := requestType == schemas.ImageGenerationStreamRequest || requestType == schemas.ImageEditStreamRequest
	isPassthroughStreaming := requestType == schemas.PassthroughStreamRequest

	if isChatStreaming {
		// Handle text-based streaming with ordered accumulation
		return a.processChatStreamingResponse(ctx, result, bifrostErr)
	} else if isAudioStreaming {
		// Handle speech/transcription streaming with original flow
		if requestType == schemas.TranscriptionStreamRequest {
			return a.processTranscriptionStreamingResponse(ctx, result, bifrostErr)
		}
		if requestType == schemas.SpeechStreamRequest {
			return a.processAudioStreamingResponse(ctx, result, bifrostErr)
		}
	} else if isResponsesStreaming {
		// Handle responses streaming with responses accumulation
		return a.processResponsesStreamingResponse(ctx, result, bifrostErr)
	} else if isImageStreaming {
		// Handle image streaming
		return a.processImageStreamingResponse(ctx, result, bifrostErr)
	} else if isPassthroughStreaming {
		// Handle passthrough streaming with raw body accumulation
		return a.processPassthroughStreamingResponse(ctx, result, bifrostErr)
	}
	return nil, fmt.Errorf("request type missing/invalid for accumulator: %s", requestType)
}

// Cleanup cleans up the accumulator
func (a *Accumulator) Cleanup() {
	a.streamAccumulators.Range(func(key, value interface{}) bool {
		accumulator := value.(*StreamAccumulator)
		accumulator.mu.Lock()
		a.cleanupStreamAccumulator(key.(string), true)
		accumulator.mu.Unlock()
		return true
	})
	a.cleanupOnce.Do(func() {
		close(a.stopCleanup)
	})
	a.cleanupTicker.Stop()
	a.cleanupWg.Wait()
}

// CreateStreamAccumulator creates a new stream accumulator for a request
// It increments the reference counter atomically for concurrent access tracking
func (a *Accumulator) CreateStreamAccumulator(requestID string, startTimestamp time.Time) *StreamAccumulator {
	a.endedStreamIDs.Delete(requestID)
	sc := a.getOrCreateStreamAccumulator(requestID)
	// Atomically increment reference counter
	sc.refCount.Add(1)
	// Lock before writing to StartTimestamp
	sc.mu.Lock()
	sc.StartTimestamp = startTimestamp
	sc.mu.Unlock()
	return sc
}

// CleanupStreamAccumulator decrements the reference counter for a stream accumulator.
// The accumulator is only cleaned up when the reference counter reaches 0.
// This function is idempotent - calling it after cleanup has already happened is safe.
func (a *Accumulator) CleanupStreamAccumulator(requestID string) error {
	acc, exists := a.streamAccumulators.Load(requestID)
	if !exists {
		// Accumulator already cleaned up - this is expected when multiple callers
		// (e.g., completeDeferredSpan and HTTP middleware) both call cleanup
		return nil
	}
	if accumulator, ok := acc.(*StreamAccumulator); ok {
		// Atomically decrement reference counter
		newCount := accumulator.refCount.Add(-1)
		// Only cleanup when reference counter reaches 0
		if newCount <= 0 {
			accumulator.mu.Lock()
			defer accumulator.mu.Unlock()
			a.cleanupStreamAccumulator(requestID, false) // natural completion — defer if gate is still busy
		}
	}
	return nil
}

// ForceCleanupStreamAccumulator reaps a stream accumulator regardless of its
// reference counter. It is the guaranteed end-of-stream backstop: callers invoke
// it from the stream's terminal lifecycle hook (the provider goroutine's
// finalizer), at which point the stream has stopped delivering chunks and the
// per-plugin refcount handshake may be incomplete (e.g. a client abort that
// never produced a terminal chunk, or multiple plugins that each Create but not
// all Cleanup). Force-reaping here mirrors the TTL sweep (cleanupOldAccumulators),
// which already deletes with forceEndGate=true. Idempotent and safe to call after
// CleanupStreamAccumulator has already freed the entry.
func (a *Accumulator) ForceCleanupStreamAccumulator(requestID string) {
	acc, exists := a.streamAccumulators.Load(requestID)
	if !exists {
		return
	}
	accumulator, ok := acc.(*StreamAccumulator)
	if !ok {
		return
	}
	accumulator.mu.Lock()
	defer accumulator.mu.Unlock()
	a.cleanupStreamAccumulator(requestID, true) // stream is over — force-end the gate and reap
}

// cleanupOldAccumulators removes old accumulators
func (a *Accumulator) cleanupOldAccumulators() {
	count := 0
	cutoff := time.Now().Add(-a.ttl)
	a.streamAccumulators.Range(func(key, value interface{}) bool {
		accumulator := value.(*StreamAccumulator)
		accumulator.mu.Lock()
		defer accumulator.mu.Unlock()
		if accumulator.Timestamp.Before(cutoff) {
			a.cleanupStreamAccumulator(key.(string), true) // orphan TTL reap — force-end gate
		}
		count++
		return true
	})
	a.endedStreamIDs.Range(func(key, value interface{}) bool {
		if endedAt, ok := value.(time.Time); ok && endedAt.Before(cutoff) {
			a.endedStreamIDs.Delete(key)
		}
		return true
	})

	a.logger.Debug("[streaming] cleanup old accumulators done. current size: %d entries", count)
}

// startCleanup runs in a background goroutine to periodically remove expired entries
func (a *Accumulator) startAccumulatorMapCleanup() {
	defer a.cleanupWg.Done()

	for {
		select {
		case <-a.cleanupTicker.C:
			a.cleanupOldAccumulators()
		case <-a.stopCleanup:
			return
		}
	}
}

// NewAccumulator creates a new accumulator
func NewAccumulator(pricingManager *modelcatalog.ModelCatalog, logger schemas.Logger) *Accumulator {
	return NewAccumulatorWithOptions(pricingManager, logger, DefaultAccumulatorOptions())
}

// NewAccumulatorWithOptions creates a new accumulator with explicit retention options.
func NewAccumulatorWithOptions(pricingManager *modelcatalog.ModelCatalog, logger schemas.Logger, options AccumulatorOptions) *Accumulator {
	a := &Accumulator{
		streamAccumulators: sync.Map{},
		chatStreamChunkPool: sync.Pool{
			New: func() any {
				return &ChatStreamChunk{}
			},
		},
		responsesStreamChunkPool: sync.Pool{
			New: func() any {
				return &ResponsesStreamChunk{}
			},
		},
		audioStreamChunkPool: sync.Pool{
			New: func() any {
				return &AudioStreamChunk{}
			},
		},
		transcriptionStreamChunkPool: sync.Pool{
			New: func() any {
				return &TranscriptionStreamChunk{}
			},
		},
		imageStreamChunkPool: sync.Pool{
			New: func() any {
				return &ImageStreamChunk{}
			},
		},
		pricingManager: pricingManager,
		logger:         logger,
		ttl:            30 * time.Minute,
		cleanupTicker:  time.NewTicker(1 * time.Minute),
		cleanupWg:      sync.WaitGroup{},
		stopCleanup:    make(chan struct{}),
		options:        options,
	}
	a.cleanupWg.Add(1)
	// Prewarm the pools for better performance at startup
	for range 1000 {
		a.chatStreamChunkPool.Put(&ChatStreamChunk{})
		a.responsesStreamChunkPool.Put(&ResponsesStreamChunk{})
		a.audioStreamChunkPool.Put(&AudioStreamChunk{})
		a.transcriptionStreamChunkPool.Put(&TranscriptionStreamChunk{})
		a.imageStreamChunkPool.Put(&ImageStreamChunk{})
	}
	go a.startAccumulatorMapCleanup()
	return a
}
