# PgBouncer in transaction-pooling mode (ADR-15). Built from Alpine so the
# configuration is fully owned by this repository.
FROM alpine:3.22

# The Alpine package does not create a service user, so the image defines its own
# non-root user (same uid/gid convention as the backend and frontend images).
RUN apk add --no-cache pgbouncer postgresql16-client \
    && addgroup -S -g 10001 app \
    && adduser -S -D -H -u 10001 -G app -s /sbin/nologin app \
    && mkdir -p /etc/pgbouncer /var/run/pgbouncer \
    && chown -R app:app /etc/pgbouncer /var/run/pgbouncer

COPY pgbouncer.ini.template /etc/pgbouncer/pgbouncer.ini.template
COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh

USER app
EXPOSE 6432
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD pg_isready -h 127.0.0.1 -p 6432 -U "$DB_USER" -d "$DB_NAME" || exit 1
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
