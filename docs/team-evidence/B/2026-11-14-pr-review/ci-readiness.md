# CI startup race found during PR verification

The first PR run on `041081e81332967c44225b314c6b8fa9f372eaaf` failed during
isolated PostgreSQL startup, before application tests. The recorded job showed:

```text
06:19:48 /var/run/postgresql:5432 - no response
06:19:49 /var/run/postgresql:5432 - accepting connections
06:19:49 /var/run/postgresql:5432 - no response
Process completed with exit code 2.
```

Source: [failed PR workflow job](https://github.com/alpiex1336-code/CargoPulse/actions/runs/43565728753/job/132359049276).
The official PostgreSQL image starts a temporary Unix-socket initialization
server, stops it, then starts the final network server. The old socket readiness
probe could succeed against that temporary server; its immediate second probe
then ran during the shutdown gap. This explains the observed sequence and is
consistent with the [upstream entrypoint](https://github.com/docker-library/postgres/blob/master/docker-entrypoint.sh).

The workflow now probes the final TCP listener at `127.0.0.1:5432`, with the same
bounded retry loop and mandatory final probe. No test or security gate is skipped.
Failure logging handles a missing development .env, and cleanup checks which
isolated containers actually exist instead of failing again on absent services.

This is a narrow workflow repair prompted by executed CI. The subsequent run on
the updated PR head must pass before the PR is marked ready; the first failed run
remains visible in GitHub's history. No production configuration is changed.
