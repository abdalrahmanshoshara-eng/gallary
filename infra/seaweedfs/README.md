# SeaweedFS (S3-compatible object storage) — ADR-17

`s3.dev.json` holds **development-only** credentials (they are not secrets; the dev stack
is not reachable from outside your machine).

- `app` — the key Django uses (read/write both buckets).
- `anonymous` — read-only access to `damascene-public` (processed image variants), so
  browsers can load images directly. Listing is not granted, so files cannot be enumerated.
  The private bucket (original uploads with EXIF/GPS) has no anonymous access.

Production: use a managed S3 provider if available, or run SeaweedFS with
`docker-compose.prod.yml --profile self-hosted-storage` and an `s3.json` kept **outside
the repository** (path in `SEAWEEDFS_S3_CONFIG`), with long random keys.
