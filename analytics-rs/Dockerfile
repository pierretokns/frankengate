# syntax=docker/dockerfile:1.7
FROM rust:1.85-alpine3.21@sha256:4333721398de61f53ccbe53b0b855bcc4bb49e55828e8f652d7a8ac33dd0c118 AS builder
WORKDIR /src
RUN apk add --no-cache musl-dev
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release --locked --bin frankengate-analytics-control

FROM alpine:3.21@sha256:48b0309ca019d89d40f670aa1bc06e426dc0931948452e8491e3d65087abc07d
RUN adduser -D -s /sbin/nologin appuser
COPY --from=builder /src/target/release/frankengate-analytics-control /usr/local/bin/frankengate-analytics-control
USER appuser
ENTRYPOINT ["/usr/local/bin/frankengate-analytics-control"]
