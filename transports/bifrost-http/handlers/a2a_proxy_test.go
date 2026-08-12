package handlers

import (
	"context"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/fasthttp/router"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2adiscovery"
	"github.com/valyala/fasthttp"
)

func TestA2AProxyCardRewriteAndJSONPassthrough(t *testing.T) {
	var observed atomic.Int32
	var observedInfo a2adiscovery.ProxyResponseInfo
	proxyURL, closeServers := newA2AProxyTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/agent/.well-known/agent-card.json" {
			w.Header().Set("Content-Type", "application/agent-card+json")
			_, _ = io.WriteString(w, `{"name":"upstream","supportedInterfaces":[{"protocolBinding":"JSONRPC","url":"https://upstream.example/a2a"}]}`)
			return
		}
		if r.URL.Path != "/agent/a2a" || r.Method != http.MethodPost {
			http.NotFound(w, r)
			return
		}
		body, _ := io.ReadAll(r.Body)
		if string(body) != `{"jsonrpc":"2.0","method":"message/send","params":{"x":1}}` {
			t.Errorf("upstream body = %q", body)
		}
		if r.Header.Get("X-Correlation-ID") != "request-1" {
			t.Errorf("upstream did not receive forwarded request header")
		}
		w.Header().Set("Content-Type", "application/a2a+json; charset=utf-8")
		_, _ = io.WriteString(w, `{"result":{"kind":"task","status":{"state":"completed"}}}`)
	}, A2AProxyOptions{
		ResponseObserver: func(_ a2adiscovery.ProxyRequestClassification, info a2adiscovery.ProxyResponseInfo) {
			observedInfo = info
			observed.Add(1)
		},
	})
	defer closeServers()

	cardResp := mustProxyRequest(t, http.MethodGet, proxyURL+"/a2a/proxy/.well-known/agent-card.json", nil, "")
	if cardResp.StatusCode != http.StatusOK {
		t.Fatalf("card status = %d, body=%s", cardResp.StatusCode, cardResp.Body)
	}
	var card map[string]any
	if err := json.Unmarshal(cardResp.Body, &card); err != nil {
		t.Fatal(err)
	}
	interfaces := card["supportedInterfaces"].([]any)
	if got := interfaces[0].(map[string]any)["url"]; got != "https://gateway.example/a2a/proxy/a2a" {
		t.Fatalf("rewritten interface URL = %v", got)
	}

	callBody := `{"jsonrpc":"2.0","method":"message/send","params":{"x":1}}`
	callResp := mustProxyRequest(t, http.MethodPost, proxyURL+"/a2a/proxy/a2a", strings.NewReader(callBody), "request-1")
	if callResp.StatusCode != http.StatusOK || string(callResp.Body) != `{"result":{"kind":"task","status":{"state":"completed"}}}` {
		t.Fatalf("call response = %d %q", callResp.StatusCode, callResp.Body)
	}
	if observed.Load() != 1 || observedInfo.Outcome != a2adiscovery.ProxyResponseSuccess || observedInfo.TaskState != "completed" {
		t.Fatalf("response observation = count %d info %#v", observed.Load(), observedInfo)
	}
}

func TestA2AProxyPassthroughSSEAndOversizedJSON(t *testing.T) {
	var observed atomic.Int32
	proxyURL, closeServers := newA2AProxyTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/agent/a2a/stream":
			w.Header().Set("Content-Type", "text/event-stream")
			flusher, _ := w.(http.Flusher)
			_, _ = io.WriteString(w, "data: first\n\n")
			if flusher != nil {
				flusher.Flush()
			}
			_, _ = io.WriteString(w, "data: second\n\n")
		case "/agent/a2a/large":
			w.Header().Set("Content-Type", "application/json")
			_, _ = io.WriteString(w, `{"result":{"kind":"task","status":{"state":"completed"}},"padding":"0123456789"}`)
		default:
			http.NotFound(w, r)
		}
	}, A2AProxyOptions{MaxResponseBytes: 32, ResponseObserver: func(_ a2adiscovery.ProxyRequestClassification, _ a2adiscovery.ProxyResponseInfo) {
		observed.Add(1)
	}})
	defer closeServers()

	sse := mustProxyRequest(t, http.MethodPost, proxyURL+"/a2a/proxy/a2a/stream", strings.NewReader(`{"jsonrpc":"2.0"}`), "")
	if got := string(sse.Body); got != "data: first\n\ndata: second\n\n" {
		t.Fatalf("SSE body = %q", got)
	}

	large := mustProxyRequest(t, http.MethodPost, proxyURL+"/a2a/proxy/a2a/large", strings.NewReader(`{"jsonrpc":"2.0"}`), "")
	wantLarge := `{"result":{"kind":"task","status":{"state":"completed"}},"padding":"0123456789"}`
	if string(large.Body) != wantLarge {
		t.Fatalf("oversized JSON body changed: %q", large.Body)
	}
	if observed.Load() != 0 {
		t.Fatal("oversized JSON response was inspected")
	}
}

func TestA2AProxyRejectsBodyDeadlineAllowlistAndSSRFViolations(t *testing.T) {
	var calls atomic.Int32
	proxyURL, closeServers := newA2AProxyTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		if r.URL.Path == "/agent/slow" {
			time.Sleep(100 * time.Millisecond)
		}
		_, _ = io.WriteString(w, `{"result":{}}`)
	}, A2AProxyOptions{MaxRequestBytes: 4})
	defer closeServers()

	tooLarge := mustProxyRequest(t, http.MethodPost, proxyURL+"/a2a/proxy/a2a", strings.NewReader("12345"), "")
	if tooLarge.StatusCode != http.StatusRequestEntityTooLarge {
		t.Fatalf("oversized request status = %d", tooLarge.StatusCode)
	}
	if calls.Load() != 0 {
		t.Fatal("oversized request reached upstream")
	}

	deadlineURL, closeDeadline := newA2AProxyTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(100 * time.Millisecond)
		_, _ = io.WriteString(w, `{"result":{}}`)
	}, A2AProxyOptions{Timeout: 20 * time.Millisecond})
	defer closeDeadline()
	deadline := mustProxyRequest(t, http.MethodPost, deadlineURL+"/a2a/proxy/slow", strings.NewReader("{}"), "")
	if deadline.StatusCode != http.StatusBadGateway {
		t.Fatalf("deadline status = %d", deadline.StatusCode)
	}

	deniedURL, closeDenied := newA2AProxyTestServerWithTarget(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, `{"result":{}}`)
	}, A2AProxyOptions{AllowedHosts: []string{"other.example"}})
	defer closeDenied()
	denied := mustProxyRequest(t, http.MethodPost, deniedURL+"/a2a/proxy/a2a", strings.NewReader("{}"), "")
	if denied.StatusCode != http.StatusBadGateway {
		t.Fatalf("allowlist status = %d", denied.StatusCode)
	}

	ssrfURL, closeSSRF := newA2AProxyTestServerWithTarget(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, `{"result":{}}`)
	}, A2AProxyOptions{UpstreamURL: "http://127.0.0.1:1/.well-known/agent-card.json", AllowedHosts: []string{"127.0.0.1"}})
	defer closeSSRF()
	ssrf := mustProxyRequest(t, http.MethodPost, ssrfURL+"/a2a/proxy/a2a", strings.NewReader("{}"), "")
	if ssrf.StatusCode != http.StatusBadGateway {
		t.Fatalf("SSRF status = %d", ssrf.StatusCode)
	}
}

func TestNewA2AProxyHandlerRequiresAllowlist(t *testing.T) {
	if _, err := NewA2AProxyHandler(A2AProxyOptions{UpstreamURL: "https://agent.example"}); err == nil {
		t.Fatal("proxy without an allowlist was accepted")
	}
}

func TestA2AProxyCredentialForwardingIsExplicit(t *testing.T) {
	var authorization, cookie atomic.Value
	proxyURL, closeServers := newA2AProxyTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		authorization.Store(r.Header.Get("Authorization"))
		cookie.Store(r.Header.Get("Cookie"))
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"result":{}}`)
	}, A2AProxyOptions{})
	defer closeServers()

	request := fasthttp.AcquireRequest()
	defer fasthttp.ReleaseRequest(request)
	response := fasthttp.AcquireResponse()
	defer fasthttp.ReleaseResponse(response)
	request.SetRequestURI(proxyURL + "/a2a/proxy/a2a")
	request.Header.SetMethod(http.MethodPost)
	request.Header.SetContentType("application/json")
	request.Header.Set("Authorization", "Bearer secret")
	request.Header.Set("Cookie", "session=secret")
	request.SetBodyString("{}")
	if err := (&fasthttp.Client{}).Do(request, response); err != nil {
		t.Fatal(err)
	}
	if got := authorization.Load().(string); got != "" {
		t.Fatalf("authorization forwarded without opt-in: %q", got)
	}
	if got := cookie.Load().(string); got != "" {
		t.Fatalf("cookie forwarded without opt-in: %q", got)
	}

	var forwardedAuthorization, forwardedCookie atomic.Value
	forwardURL, closeForward := newA2AProxyTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		forwardedAuthorization.Store(r.Header.Get("Authorization"))
		forwardedCookie.Store(r.Header.Get("Cookie"))
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"result":{}}`)
	}, A2AProxyOptions{ForwardAuthorization: true, ForwardCookies: true})
	defer closeForward()
	request = fasthttp.AcquireRequest()
	defer fasthttp.ReleaseRequest(request)
	response = fasthttp.AcquireResponse()
	defer fasthttp.ReleaseResponse(response)
	request.SetRequestURI(forwardURL + "/a2a/proxy/a2a")
	request.Header.SetMethod(http.MethodPost)
	request.Header.SetContentType("application/json")
	request.Header.Set("Authorization", "Bearer secret")
	request.Header.Set("Cookie", "session=secret")
	request.SetBodyString("{}")
	if err := (&fasthttp.Client{}).Do(request, response); err != nil {
		t.Fatal(err)
	}
	if got := forwardedAuthorization.Load().(string); got != "Bearer secret" {
		t.Fatalf("authorization opt-in forwarding = %q", got)
	}
	if got := forwardedCookie.Load().(string); got != "session=secret" {
		t.Fatalf("cookie opt-in forwarding = %q", got)
	}
}

type proxyHTTPResponse struct {
	StatusCode int
	Body       []byte
}

func mustProxyRequest(t *testing.T, method, target string, body io.Reader, correlationID string) proxyHTTPResponse {
	t.Helper()
	var requestBody []byte
	if body != nil {
		var err error
		requestBody, err = io.ReadAll(body)
		if err != nil {
			t.Fatal(err)
		}
	}
	req := fasthttp.AcquireRequest()
	defer fasthttp.ReleaseRequest(req)
	resp := fasthttp.AcquireResponse()
	defer fasthttp.ReleaseResponse(resp)
	req.SetRequestURI(target)
	req.Header.SetMethod(method)
	req.Header.SetContentType("application/json")
	req.SetBody(requestBody)
	if correlationID != "" {
		req.Header.Set("X-Correlation-ID", correlationID)
	}
	if err := (&fasthttp.Client{}).Do(req, resp); err != nil {
		t.Fatal(err)
	}
	return proxyHTTPResponse{StatusCode: resp.StatusCode(), Body: append([]byte(nil), resp.Body()...)}
}

func newA2AProxyTestServer(t *testing.T, upstreamHandler http.HandlerFunc, options A2AProxyOptions) (string, func()) {
	return newA2AProxyTestServerWithTarget(t, upstreamHandler, options)
}

func newA2AProxyTestServerWithTarget(t *testing.T, upstreamHandler http.HandlerFunc, options A2AProxyOptions) (string, func()) {
	t.Helper()
	upstream := httptest.NewServer(upstreamHandler)
	port := upstream.Listener.Addr().(*net.TCPAddr).Port
	if options.UpstreamURL == "" {
		options.UpstreamURL = "http://agent.example:" + strconv.Itoa(port) + "/agent/.well-known/agent-card.json"
	}
	if len(options.AllowedHosts) == 0 && len(options.AllowedDomains) == 0 {
		options.AllowedHosts = []string{"agent.example"}
	}
	if options.HTTPSPolicy == a2adiscovery.HTTPSOnly {
		options.HTTPSPolicy = a2adiscovery.HTTPSOrHTTP
	}
	if options.Resolver == nil {
		options.Resolver = a2adiscovery.ResolverFunc(func(context.Context, string) ([]net.IPAddr, error) {
			return []net.IPAddr{{IP: net.ParseIP("198.51.100.10")}}, nil
		})
	}
	if options.DialContext == nil {
		options.DialContext = func(ctx context.Context, network, _ string) (net.Conn, error) {
			return (&net.Dialer{}).DialContext(ctx, network, upstream.Listener.Addr().String())
		}
	}
	if options.PublicBaseURL == "" {
		options.PublicBaseURL = "https://gateway.example"
	}
	proxy, err := NewA2AProxyHandler(options)
	if err != nil {
		upstream.Close()
		t.Fatal(err)
	}
	r := router.New()
	proxy.RegisterRoutes(r)
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		upstream.Close()
		t.Fatal(err)
	}
	proxyServer := &fasthttp.Server{Handler: r.Handler}
	go func() { _ = proxyServer.Serve(listener) }()
	proxyURL := "http://" + listener.Addr().String()
	return proxyURL, func() {
		_ = proxyServer.Shutdown()
		_ = listener.Close()
		upstream.Close()
	}
}
