FROM golang:1.26.5 AS build
WORKDIR /src
COPY go.mod go.sum* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /out/frankengate-analytics ./cmd/frankengate-analytics

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/frankengate-analytics /frankengate-analytics
USER nonroot:nonroot
ENTRYPOINT ["/frankengate-analytics"]
