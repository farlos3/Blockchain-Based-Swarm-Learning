# The gateway image. Built by compose so the whole project is one `docker compose up`.
# Dependencies are vendored, so this builds with no network access.

FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
COPY vendor ./vendor
COPY *.go ./
COPY web ./web
RUN CGO_ENABLED=0 go build -mod=vendor -o /out/sl-gateway .

FROM alpine:3.20
RUN adduser -D -u 10001 gateway
USER gateway
COPY --from=build /out/sl-gateway /usr/local/bin/sl-gateway
# inside the compose network the gateway reaches peers by container name, not localhost
ENV SL_IN_CLUSTER=1
EXPOSE 8899
ENTRYPOINT ["sl-gateway"]
