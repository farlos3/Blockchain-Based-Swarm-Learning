# The chaincode image, built once on the host and run as a service per organization.
# Dependencies are vendored, so this builds with no network access.

FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
COPY vendor ./vendor
COPY *.go ./
RUN CGO_ENABLED=0 go build -mod=vendor -o /out/sl-ledger .

FROM alpine:3.20
RUN adduser -D -u 10000 chaincode
USER chaincode
COPY --from=build /out/sl-ledger /usr/local/bin/sl-ledger
EXPOSE 9999
ENTRYPOINT ["sl-ledger"]
