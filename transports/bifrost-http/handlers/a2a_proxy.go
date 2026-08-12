package handlers

import (
	"bufio"
	"bytes"
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"io"
	"mime"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/fasthttp/router"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/modelcatalog/a2adiscovery"
	"github.com/maximhq/bifrost/transports/bifrost-http/lib"
	"github.com/valyala/fasthttp"
)

const (
	defaultA2AProxyRoutePrefix = "/a2a/proxy"
	defaultA2AProxyRequestSize = 128 * 1024
)

// A2AProxyResponseObserver receives only the bounded response projection
// produced by a2adiscovery.InspectA2AJSONResponse. It never receives the
// response body, request payload, destination URL, or credentials.
type A2AProxyResponseObserver func(a2adiscovery.ProxyRequestClassification, a2adiscovery.ProxyResponseInfo)

// A2AProxyOptions configures an explicit, operator-installed transparent A2A
// route. UpstreamURL is either an Agent Card URL or the upstream agent path;
// calls are sent to the upstream origin using the path selected by the
// rewritten card. AllowedHosts or AllowedDomains is mandatory.
type A2AProxyOptions struct {
	RoutePrefix   string
	UpstreamURL   string
	PublicBaseURL string

	MaxRequestBytes      int64
	MaxResponseBytes     int
	Timeout              time.Duration
	HTTPSPolicy          a2adiscovery.HTTPSPolicy
	MaxRedirects         int
	AllowedHosts         []string
	AllowedDomains       []string
	Resolver             a2adiscovery.Resolver
	DialContext          a2adiscovery.DialContextFunc
	TLSClientConfig      *tls.Config
	ForwardAuthorization bool
	ForwardCookies       bool

	ResponseObserver A2AProxyResponseObserver
}

// A2AProxyHandler is a live Agentgateway-compatible A2A edge proxy. It is
// intentionally opt-in: constructing and registering one requires an
// upstream URL and an explicit DNS/host allowlist.
type A2AProxyHandler struct {
	routePrefix          string
	upstreamCard         *url.URL
	upstreamOrigin       *url.URL
	publicBase           *url.URL
	maxRequest           int64
	maxResponse          int
	timeout              time.Duration
	client               *http.Client
	observer             A2AProxyResponseObserver
	forwardAuthorization bool
	forwardCookies       bool
}

// NewA2AProxyHandler validates the proxy configuration and builds a client
// with the same SSRF-resistant resolver and redirect policy as A2A discovery.
func NewA2AProxyHandler(options A2AProxyOptions) (*A2AProxyHandler, error) {
	routePrefix := strings.TrimSpace(options.RoutePrefix)
	if routePrefix == "" {
		routePrefix = defaultA2AProxyRoutePrefix
	}
	if !strings.HasPrefix(routePrefix, "/") || strings.HasSuffix(routePrefix, "/") || strings.Contains(routePrefix, "?") {
		return nil, errors.New("A2A proxy route prefix must be an absolute path without a trailing slash or query")
	}

	upstream, err := parseA2AProxyURL(options.UpstreamURL)
	if err != nil {
		return nil, fmt.Errorf("A2A proxy upstream: %w", err)
	}
	card := *upstream
	basePath := card.Path
	if strings.HasSuffix(basePath, a2adiscovery.LegacyAgentCardPath) {
		basePath = strings.TrimSuffix(basePath, a2adiscovery.LegacyAgentCardPath)
	} else if strings.HasSuffix(basePath, a2adiscovery.WellKnownAgentCardPath) {
		basePath = strings.TrimSuffix(basePath, a2adiscovery.WellKnownAgentCardPath)
	} else {
		card.Path = appendA2APath(basePath, a2adiscovery.WellKnownAgentCardPath)
		card.RawPath = ""
	}
	if card.Path == "" {
		card.Path = a2adiscovery.WellKnownAgentCardPath
	}
	card.RawPath = ""

	origin := *upstream
	origin.Path = basePath
	origin.RawPath = ""
	origin.ForceQuery = false

	var publicBase *url.URL
	if strings.TrimSpace(options.PublicBaseURL) != "" {
		publicBase, err = parseA2AProxyURL(options.PublicBaseURL)
		if err != nil {
			return nil, fmt.Errorf("A2A proxy public base: %w", err)
		}
		publicBase.Path = strings.TrimRight(publicBase.Path, "/")
		publicBase.RawPath = ""
	}

	maxRequest := options.MaxRequestBytes
	if maxRequest <= 0 {
		maxRequest = defaultA2AProxyRequestSize
	}
	maxResponse := options.MaxResponseBytes
	if maxResponse <= 0 {
		maxResponse = a2adiscovery.DefaultMaxResponseBytes
	}
	timeout := options.Timeout
	if timeout <= 0 {
		timeout = time.Duration(a2adiscovery.DefaultTimeoutMillis) * time.Millisecond
	}
	client, err := a2adiscovery.NewProxyHTTPClient(a2adiscovery.Options{
		Timeout:         timeout,
		HTTPSPolicy:     options.HTTPSPolicy,
		MaxRedirects:    options.MaxRedirects,
		AllowedHosts:    options.AllowedHosts,
		AllowedDomains:  options.AllowedDomains,
		Resolver:        options.Resolver,
		DialContext:     options.DialContext,
		TLSClientConfig: options.TLSClientConfig,
	})
	if err != nil {
		return nil, fmt.Errorf("A2A proxy client: %w", err)
	}
	return &A2AProxyHandler{
		routePrefix:          routePrefix,
		upstreamCard:         &card,
		upstreamOrigin:       &origin,
		publicBase:           publicBase,
		maxRequest:           maxRequest,
		maxResponse:          maxResponse,
		timeout:              timeout,
		client:               client,
		observer:             options.ResponseObserver,
		forwardAuthorization: options.ForwardAuthorization,
		forwardCookies:       options.ForwardCookies,
	}, nil
}

// RegisterRoutes adds only the configured proxy prefix. No route is installed
// unless the caller explicitly constructs and registers this handler.
func (h *A2AProxyHandler) RegisterRoutes(r *router.Router, middlewares ...schemas.BifrostHTTPMiddleware) {
	if h == nil || r == nil {
		return
	}
	handler := lib.ChainMiddlewares(h.handle, middlewares...)
	r.GET(h.routePrefix, handler)
	r.GET(h.routePrefix+"/{path:*}", handler)
	r.POST(h.routePrefix, handler)
	r.POST(h.routePrefix+"/{path:*}", handler)
}

func (h *A2AProxyHandler) handle(ctx *fasthttp.RequestCtx) {
	method := string(ctx.Method())
	if method != http.MethodGet && method != http.MethodPost {
		SendError(ctx, fasthttp.StatusMethodNotAllowed, "A2A proxy supports GET and POST")
		return
	}
	body := ctx.Request.Body()
	if ctx.Request.IsBodyStream() {
		streamBody, err := io.ReadAll(io.LimitReader(ctx.RequestBodyStream(), h.maxRequest+1))
		if err != nil {
			SendError(ctx, fasthttp.StatusBadRequest, "A2A proxy could not read the request body")
			return
		}
		body = streamBody
	}
	if int64(len(body)) > h.maxRequest {
		SendError(ctx, fasthttp.StatusRequestEntityTooLarge, "A2A proxy request body exceeds the configured limit")
		return
	}

	requestPath := string(ctx.Request.URI().PathOriginal())
	if requestPath == "" {
		requestPath = string(ctx.Path())
	}
	if !strings.HasPrefix(requestPath, h.routePrefix) {
		SendError(ctx, fasthttp.StatusNotFound, "A2A proxy route not found")
		return
	}
	suffix := strings.TrimPrefix(requestPath, h.routePrefix)
	if suffix == "" {
		suffix = "/"
	}
	if err := validateA2AProxyPath(suffix); err != nil {
		SendError(ctx, fasthttp.StatusBadRequest, err.Error())
		return
	}

	classification := a2adiscovery.ClassifyProxyRequest(
		method,
		requestPath,
		string(ctx.Request.Header.ContentType()),
		body,
		requestPublicURL(ctx, requestPath),
		string(ctx.Request.Header.Peek("X-Forwarded-Proto")),
	)
	target := h.targetURL(ctx, suffix, classification.Kind == a2adiscovery.ProxyRequestAgentCard)
	if target == nil {
		SendError(ctx, fasthttp.StatusBadGateway, "A2A proxy could not build the upstream URL")
		return
	}

	requestContext, cancel := context.WithTimeout(context.Background(), h.timeout)
	req, err := http.NewRequestWithContext(requestContext, method, target.String(), bytes.NewReader(body))
	if err != nil {
		cancel()
		SendError(ctx, fasthttp.StatusBadGateway, "A2A proxy could not create the upstream request")
		return
	}
	copyRequestHeaders(&ctx.Request.Header, &req.Header, h.forwardAuthorization, h.forwardCookies)
	req.Header.Set("Accept-Encoding", "identity")
	req.ContentLength = int64(len(body))

	resp, err := h.client.Do(req)
	if err != nil {
		cancel()
		SendError(ctx, fasthttp.StatusBadGateway, "A2A upstream is unavailable")
		return
	}

	if classification.Kind == a2adiscovery.ProxyRequestAgentCard && resp.StatusCode >= 200 && resp.StatusCode < 300 {
		h.handleAgentCard(ctx, resp, requestPath, cancel)
		return
	}
	h.handleCallResponse(ctx, resp, classification, cancel)
}

func (h *A2AProxyHandler) handleAgentCard(ctx *fasthttp.RequestCtx, resp *http.Response, requestPath string, cancel context.CancelFunc) {
	defer resp.Body.Close()
	defer cancel()
	if strings.TrimSpace(resp.Header.Get("Content-Encoding")) != "" {
		SendError(ctx, fasthttp.StatusBadGateway, "A2A Agent Card uses unsupported content encoding")
		return
	}
	body, complete, overflow, err := readA2AProxyBody(resp.Body, h.maxResponse)
	if err != nil || overflow || !complete {
		SendError(ctx, fasthttp.StatusBadGateway, "A2A Agent Card exceeds the configured response limit")
		return
	}
	gatewayBase, err := h.gatewayBase(ctx, requestPath)
	if err != nil {
		SendError(ctx, fasthttp.StatusBadGateway, "A2A proxy public URL is not configured correctly")
		return
	}
	rewritten, err := a2adiscovery.RewriteAgentCardForGateway(body, gatewayBase, h.maxResponse)
	if err != nil {
		SendError(ctx, fasthttp.StatusBadGateway, "A2A upstream returned an invalid Agent Card")
		return
	}
	copyResponseHeaders(resp, ctx)
	ctx.SetStatusCode(resp.StatusCode)
	ctx.SetBody(rewritten)
}

func (h *A2AProxyHandler) handleCallResponse(ctx *fasthttp.RequestCtx, resp *http.Response, classification a2adiscovery.ProxyRequestClassification, cancel context.CancelFunc) {
	if isA2AJSONContentType(resp.Header.Get("Content-Type")) && (resp.ContentLength < 0 || resp.ContentLength <= int64(h.maxResponse)) {
		body, complete, overflow, err := readA2AProxyBody(resp.Body, h.maxResponse)
		if err == nil && complete && !overflow {
			defer resp.Body.Close()
			defer cancel()
			copyResponseHeaders(resp, ctx)
			ctx.SetStatusCode(resp.StatusCode)
			ctx.SetBody(body)
			if h.observer != nil {
				if info, ok := a2adiscovery.InspectA2AJSONResponse(body, resp.Header.Get("Content-Type"), true, h.maxResponse); ok {
					h.observer(classification, info)
				}
			}
			return
		}
		// An unknown-length JSON body may exceed the inspection cap. The prefix
		// is retained and the remainder is streamed without parsing.
		if overflow {
			h.streamResponse(ctx, resp, bytes.NewReader(body), cancel)
			return
		}
		if len(body) > 0 {
			h.streamResponse(ctx, resp, bytes.NewReader(body), cancel)
			return
		}
	}
	h.streamResponse(ctx, resp, nil, cancel)
}

func (h *A2AProxyHandler) streamResponse(ctx *fasthttp.RequestCtx, resp *http.Response, prefix io.Reader, cancel context.CancelFunc) {
	copyResponseHeaders(resp, ctx)
	ctx.SetStatusCode(resp.StatusCode)
	if resp.ContentLength < 0 {
		ctx.Response.Header.Del("Content-Length")
	}
	ctx.SetBodyStreamWriter(func(w *bufio.Writer) {
		defer resp.Body.Close()
		defer cancel()
		reader := io.Reader(resp.Body)
		if prefix != nil {
			reader = io.MultiReader(prefix, resp.Body)
		}
		_, _ = io.Copy(w, reader)
	})
}

func (h *A2AProxyHandler) targetURL(ctx *fasthttp.RequestCtx, suffix string, card bool) *url.URL {
	var target url.URL
	if card {
		target = *h.upstreamCard
	} else {
		target = *h.upstreamOrigin
		parsed, err := url.ParseRequestURI(suffix)
		if err != nil {
			return nil
		}
		target.Path = appendA2APath(target.Path, parsed.Path)
		target.RawPath = ""
		if parsed.RawQuery != "" {
			target.RawQuery = parsed.RawQuery
		}
	}
	query := string(ctx.Request.URI().QueryString())
	if query != "" {
		if target.RawQuery != "" {
			target.RawQuery += "&" + query
		} else {
			target.RawQuery = query
		}
	}
	return &target
}

func (h *A2AProxyHandler) gatewayBase(ctx *fasthttp.RequestCtx, requestPath string) (string, error) {
	if h.publicBase != nil {
		base := *h.publicBase
		base.Path = strings.TrimRight(base.Path, "/") + h.routePrefix
		base.RawPath = ""
		return a2adiscovery.BuildGatewayAgentPath(base.String() + a2adiscovery.WellKnownAgentCardPath)
	}
	scheme := strings.TrimSpace(strings.SplitN(string(ctx.Request.Header.Peek("X-Forwarded-Proto")), ",", 2)[0])
	if scheme != "http" && scheme != "https" {
		if ctx.IsTLS() {
			scheme = "https"
		} else {
			scheme = "http"
		}
	}
	host := strings.TrimSpace(string(ctx.Host()))
	if host == "" {
		return "", errors.New("request host is required")
	}
	base := (&url.URL{Scheme: scheme, Host: host, Path: h.routePrefix}).String()
	return a2adiscovery.BuildGatewayAgentPath(base + a2adiscovery.WellKnownAgentCardPath)
}

func parseA2AProxyURL(raw string) (*url.URL, error) {
	parsed, err := url.Parse(strings.TrimSpace(raw))
	if err != nil || parsed.Scheme == "" || parsed.Host == "" {
		if err == nil {
			err = errors.New("URL must be absolute")
		}
		return nil, err
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return nil, fmt.Errorf("unsupported URL scheme %q", parsed.Scheme)
	}
	if parsed.User != nil || parsed.Fragment != "" {
		return nil, errors.New("URL must not contain userinfo or a fragment")
	}
	return parsed, nil
}

func appendA2APath(base, suffix string) string {
	if suffix == "" || suffix == "/" {
		if base == "" {
			return "/"
		}
		return base
	}
	if base == "" || base == "/" {
		return "/" + strings.TrimLeft(suffix, "/")
	}
	return strings.TrimRight(base, "/") + "/" + strings.TrimLeft(suffix, "/")
}

func validateA2AProxyPath(path string) error {
	parsed, err := url.ParseRequestURI(path)
	if err != nil || !strings.HasPrefix(parsed.Path, "/") {
		return errors.New("A2A proxy path is invalid")
	}
	for _, segment := range strings.Split(parsed.Path, "/") {
		if segment == ".." {
			return errors.New("A2A proxy path traversal is not allowed")
		}
	}
	return nil
}

func requestPublicURL(ctx *fasthttp.RequestCtx, path string) string {
	scheme := "http"
	if ctx.IsTLS() {
		scheme = "https"
	}
	return (&url.URL{Scheme: scheme, Host: string(ctx.Host()), Path: path}).String()
}

func readA2AProxyBody(body io.Reader, limit int) ([]byte, bool, bool, error) {
	if limit <= 0 {
		limit = a2adiscovery.DefaultMaxResponseBytes
	}
	data, err := io.ReadAll(io.LimitReader(body, int64(limit)+1))
	if len(data) > limit {
		return data[:limit], false, true, err
	}
	return data, err == nil, false, err
}

func copyRequestHeaders(src *fasthttp.RequestHeader, dst *http.Header, forwardAuthorization, forwardCookies bool) {
	src.VisitAll(func(key, value []byte) {
		name := string(key)
		if isA2AHopByHopHeader(name) || strings.EqualFold(name, "Host") || strings.EqualFold(name, "Content-Length") {
			return
		}
		if strings.EqualFold(name, "Authorization") && !forwardAuthorization {
			return
		}
		if strings.EqualFold(name, "Cookie") && !forwardCookies {
			return
		}
		dst.Add(name, string(value))
	})
}

func copyResponseHeaders(src *http.Response, dst *fasthttp.RequestCtx) {
	for name, values := range src.Header {
		if isA2AHopByHopHeader(name) {
			continue
		}
		for _, value := range values {
			dst.Response.Header.Add(name, value)
		}
	}
}

func isA2AHopByHopHeader(name string) bool {
	switch strings.ToLower(name) {
	case "connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade":
		return true
	default:
		return false
	}
}

func isA2AJSONContentType(contentType string) bool {
	mediaType, _, err := mime.ParseMediaType(contentType)
	if err != nil {
		mediaType = strings.TrimSpace(strings.SplitN(contentType, ";", 2)[0])
	}
	switch strings.ToLower(mediaType) {
	case "application/json", "application/a2a+json":
		return true
	default:
		return false
	}
}
