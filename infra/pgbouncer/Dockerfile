# PgBouncer in transaction-pooling mode (ADR-15). Built from Alpine so the
# configuration is fully owned by this repository.
FROM alpine:3.22

RUN apk add --no-cache pgbouncer postgresql16-client \
    && mkdir -p /etc/pgbouncer /var/run/pgbouncer \
    && chown -R pgbouncer:pgbouncer /etc/pgbouncer /var/run/pgbouncer

COPY pgbouncer.ini.template /etc/pgbouncer/pgbouncer.ini.template
COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh

USER pgbouncer
EXPOSE 6432
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD pg_isready -h 127.0.0.1 -p 6432 -U "$DB_USER" -d "$DB_NAME" || exit 1
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
