# syntax=docker/dockerfile:1

FROM alpine:3.22

RUN apk add --no-cache curl

COPY test.sh /test.sh
CMD ["/bin/sh", "/test.sh"]
