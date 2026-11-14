# ADR-003/004: OIDC identity and in-app decisions

Status: accepted for implementation; production identity provisioning is external.

Production uses OIDC authorization-code flow, state, nonce and PKCE, configured
issuer/audience/JWKS and a server-side revocable session. Roles and tenant grants
come from local approved identity records, never untrusted request headers or
arbitrary OIDC claims. Privileged login requires configured MFA authentication
context. Secure HttpOnly SameSite cookies, CSRF and Origin enforcement protect
commands. The development identity adapter is explicitly enabled only in development
and must fail startup in production. It is not evidence of a production OIDC login.

Tenant checks apply to every object, job, export and stream. PostgreSQL row security
and append-only triggers provide additional protection; a privileged database owner
can still tamper and is not defeated by a hash chain.

L1 accepts synthetic data only. No external connector/write route exists. In-app
approval requires current scenario, snapshot/policy hashes, fresh data, current
validation PASS, role and compare-and-swap. Decisions are immutable. Disabled
airline adapters expose no URL fetcher. Egress policy must also deny operational
writes in the target deployment before L1 sign-off.
