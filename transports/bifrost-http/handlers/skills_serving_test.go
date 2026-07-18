package handlers

import (
	"archive/zip"
	"bytes"
	"context"
	"strings"
	"testing"

	"github.com/fasthttp/router"
	"github.com/maximhq/bifrost/framework/configstore/tables"
	"github.com/valyala/fasthttp"
)

func TestWriteZipEntryRejectsTraversalPaths(t *testing.T) {
	for _, name := range []string{"../escape.txt", "/absolute.txt", `..\\escape.txt`, "skill/../../escape.txt"} {
		var buf bytes.Buffer
		zw := zip.NewWriter(&buf)
		if err := writeZipEntry(zw, name, []byte("secret")); err == nil {
			t.Fatalf("writeZipEntry accepted unsafe path %q", name)
		}
		_ = zw.Close()
	}
}

func TestWriteZipEntryAcceptsRelativeSkillPath(t *testing.T) {
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	if err := writeZipEntry(zw, "skill/nested/file.txt", []byte("ok")); err != nil {
		t.Fatalf("writeZipEntry rejected safe path: %v", err)
	}
	if err := zw.Close(); err != nil {
		t.Fatalf("close zip: %v", err)
	}
}

func TestSafeDownloadFilenameStripsHeaderSyntax(t *testing.T) {
	got := safeDownloadFilename(`nested\\bad"name` + "\r\n" + "file.txt")
	if got == "" || got == "file.txt" || strings.ContainsAny(got, "\"\r\n\t") {
		t.Fatalf("unsafe filename was not sanitized: %q", got)
	}
}

func TestSafeDownloadFilenameHandlesUnsafeSkillName(t *testing.T) {
	got := safeDownloadFilename("skill\"\r\nname")
	if strings.ContainsAny(got, "\"\r\n\t") {
		t.Fatalf("unsafe skill name was not sanitized: %q", got)
	}
}

func TestValidForwardedHostRejectsURLInjection(t *testing.T) {
	for _, host := range []string{"", "evil.test/path", "evil.test?next=1", "evil.test\r\nX-Injected: yes", "evil test"} {
		if validForwardedHost(host) {
			t.Fatalf("accepted unsafe forwarded host %q", host)
		}
	}
	for _, host := range []string{"skills.example.test", "skills.example.test:8443", "[::1]:8080"} {
		if !validForwardedHost(host) {
			t.Fatalf("rejected valid forwarded host %q", host)
		}
	}
}

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
