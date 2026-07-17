package handlers

import (
	"context"
	"testing"

	"github.com/fasthttp/router"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/valyala/fasthttp"
)

func TestSkillsServingGenericFileDownloadDecodesEncodedPathParams(t *testing.T) {
	ctx := context.Background()
	store := newTestConfigStore(t)
	blobID := "encoded-file-blob"
	content := []byte("encoded file content")

	if err := store.CreateSkillFileBlob(ctx, &tables.TableSkillFileBlob{ID: blobID, Data: content}); err != nil {
		t.Fatalf("create blob: %v", err)
	}
	if err := store.CreateSkill(ctx, &tables.TableSkill{
		Name:        "encoded-file-skill",
		Description: "skill with encoded file paths",
		SkillMDBody: "body",
		Files: []tables.TableSkillFile{{
			Path:          "nested dir/file with spaces.txt",
			SourceType:    tables.SkillSourceTypeText,
			BlobID:        &blobID,
			MimeType:      "text/plain",
			FileSizeBytes: int64(len(content)),
		}},
	}, "1.0.0", nil); err != nil {
		t.Fatalf("create skill: %v", err)
	}

	handler := NewSkillsServingHandler(store, nil)
	r := router.New()
	handler.RegisterRoutes(r)

	// This is a path-decoding handler unit test; invoke the router directly so
	// server shutdown cannot race a database/sql context watcher after the
	// response has been written.
	request := fasthttp.AcquireRequest()
	defer fasthttp.ReleaseRequest(request)
	request.Header.SetMethod(fasthttp.MethodGet)
	request.SetRequestURI("http://test.local/api/skills/serve/encoded-file-skill/files/nested%20dir/file%20with%20spaces.txt")
	requestCtx := &fasthttp.RequestCtx{}
	requestCtx.Init(request, nil, nil)
	r.Handler(requestCtx)

	if requestCtx.Response.StatusCode() != fasthttp.StatusOK {
		t.Fatalf("status got %d, want %d; body=%s", requestCtx.Response.StatusCode(), fasthttp.StatusOK, string(requestCtx.Response.Body()))
	}
	if got := string(requestCtx.Response.Body()); got != string(content) {
		t.Fatalf("body got %q, want %q", got, string(content))
	}
}
