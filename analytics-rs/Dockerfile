# syntax=docker/dockerfile:1.7
FROM rust:1.85-alpine3.21 AS builder
WORKDIR /src
RUN apk add --no-cache musl-dev
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release --locked --bin frankengate-analytics-control

FROM alpine:3.21
RUN adduser -D -s /sbin/nologin appuser
COPY --from=builder /src/target/release/frankengate-analytics-control /usr/local/bin/frankengate-analytics-control
USER appuser
ENTRYPOINT ["/usr/local/bin/frankengate-analytics-control"]
