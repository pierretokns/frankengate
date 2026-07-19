package openai

import (
	"testing"

	"github.com/maximhq/bifrost/core/schemas"
)

func TestAudioConversionsNilSafe(t *testing.T) {
	if got := (*OpenAISpeechRequest)(nil).ToBifrostSpeechRequest(nil); got != nil {
		t.Fatalf("nil speech provider request converted to %#v", got)
	}
	if got := ToOpenAISpeechRequest(&schemas.BifrostSpeechRequest{}); got != nil {
		t.Fatalf("speech request without input converted to %#v", got)
	}
	if got := (*OpenAITranscriptionRequest)(nil).ToBifrostTranscriptionRequest(nil); got != nil {
		t.Fatalf("nil transcription provider request converted to %#v", got)
	}
	if got := ToOpenAITranscriptionRequest(&schemas.BifrostTranscriptionRequest{}); got != nil {
		t.Fatalf("transcription request without input converted to %#v", got)
	}
}

func TestAudioConversionsPreserveProviderAndModel(t *testing.T) {
	speech := (&OpenAISpeechRequest{Model: "openai/tts-1", Input: "hello"}).ToBifrostSpeechRequest(nil)
	if speech == nil || speech.Provider != schemas.OpenAI || speech.Model != "tts-1" || speech.Input.Input != "hello" {
		t.Fatalf("unexpected speech conversion: %#v", speech)
	}

	transcription := (&OpenAITranscriptionRequest{Model: "openai/whisper-1", File: []byte("audio"), Filename: "sample.wav"}).ToBifrostTranscriptionRequest(nil)
	if transcription == nil || transcription.Provider != schemas.OpenAI || transcription.Model != "whisper-1" || string(transcription.Input.File) != "audio" || transcription.Input.Filename != "sample.wav" {
		t.Fatalf("unexpected transcription conversion: %#v", transcription)
	}
}
