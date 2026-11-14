# Strict S3 Protocol XML Boundary

STATUS: Implemented and locally verified against pinned SDKs with recorded HTTP.
Real S3 deployment and external service acceptance remain unverified.

## Scope and verified SDK contracts

This work is limited to `storage.py`, the new `storage_xml.py` helper, the new
`test_storage_xml.py`, and this report. The isolated worktree baseline is
`1b003eb22427c784fe1b59fff6bfe650be120909`. It does not change upload formats,
database state, dependencies, other worktrees, credentials, grants or deployment.

VERIFIED: Installed `boto3` and `botocore` are both **1.43.127**, matching
`requirements.lock`; Python is **3.12.16**. Installed source hashes are recorded
in `.local/storage-xml/sdk-source-manifest.json`. Relevant behavior was checked
against installed source and these authoritative sources on 2026-11-12:

- [Pinned botocore parser source](https://github.com/boto/botocore/blob/1.43.127/botocore/parsers.py):
  the factory preserves timestamp/blob defaults and XML parsing passes through
  `_parse_xml_string_to_dom` on `BaseXMLResponseParser` instances.
- [Pinned session source](https://github.com/boto/botocore/blob/1.43.127/botocore/session.py)
  and [Boto3 session source](https://github.com/boto/boto3/blob/1.43.127/boto3/session.py):
  an owned botocore session can receive its own response parser factory and be
  supplied to `boto3.Session(botocore_session=...)`.
- [Pinned S3 handler source](https://github.com/boto/botocore/blob/1.43.127/botocore/handlers.py):
  `_handle_200_error` performs an earlier XML parse to recognize an error inside
  an HTTP 200 response. A response parser factory alone cannot cover that parse.
- [Pinned event implementation](https://github.com/boto/botocore/blob/1.43.127/botocore/hooks.py):
  an already registered first handler retains its position ahead of a later
  `register_first` handler. The actual ordering was also probed locally.
- [Python TreeBuilder doctype event](https://docs.python.org/3.12/library/xml.etree.elementtree.html#xml.etree.ElementTree.TreeBuilder.doctype)
  supports rejecting a DTD through the parser target, including encoding/BOM
  variations. [Python XML security documentation](https://docs.python.org/3.12/library/xml.html#xml-vulnerabilities)
  describes the standard parser's security limits; this change does not assume
  that external entities are normally resolved.

These are private SDK integration points, not a promise of compatibility with
future SDK releases. Upgrades require source review and the full transport tests.

## Implementation

`PrivateObjects` creates a fresh botocore session, installs an instance-owned
`StrictResponseParserFactory`, then constructs its S3 client through an owned
Boto3 session. The existing SDK credential chain, endpoint, TLS verification,
timeouts, bounded retries and AES256 object encryption request remain intact.
No global parser, SDK class or global event registration is changed.

The strict parser target rejects every DTD through `TreeBuilder.doctype`; entity
declarations inside a DTD therefore cannot be expanded. Malformed documents and
protocol XML exceeding **1,048,576 bytes** also fail with a generic
`ResponseParserError` that contains neither XML nor parser diagnostics. Ordinary
namespace handling, predefined XML entities, encoding behavior and parser
defaults remain delegated to the SDK/ElementTree. Non-XML factory parsers retain
their original JSON behavior.

The factory guard is paired with an earlier owned-session event boundary. The
expected pinned `_handle_200_error` registration is verified, removed only from
that owned session, and replaced with a strict-precheck wrapper which calls the
original handler for accepted input. Registration/order checks fail closed if
the expected handler or registry contract is absent. The wrapper guards nonempty
protocol/error bodies before the builtin's first XML parse and SDK body-debug
logging. It retains normal embedded-200-error conversion and retry semantics.

Successful streaming/string/blob payload operations are excluded from XML
prechecking, including successful `GetObject`. Their contents may contain XML,
DTD-like bytes, null bytes or arbitrary binary data. Existing object size and
digest verification remain unchanged. `verify()` now also converts
`ResponseParserError` to `False`; `put()` and `probe()` surface generic parse
failures, while valid service error XML retains normal SDK `ClientError` behavior.

LIMITATION: The 1 MiB check is a **protocol parsing budget after SDK buffering**,
not a limit on HTTP transfer, SDK buffering, total process memory or object
downloads. It does not implement a general untrusted XML upload parser. Successful
object downloads retain the existing separate 8,000,000-byte limit.

## Reproduction and investigation history

The initial 19-case suite ran on unchanged application source before the fix:
**13 failed, 6 passed**, saved in
`.local/storage-xml/baseline-expected-secure.txt`. Failures included accepted
internal DTDs and oversized XML, undesired parsing/error behavior, uncaught
`ResponseParserError` in `verify()`, and the expected missing new factory module.
This does not mean 13 distinct vulnerabilities or successful external entity I/O.
The baseline did not demonstrate an external file read or network entity fetch.

Two insufficient approaches were investigated rather than counted as fixes:

1. **Factory-only guard:** full SDK transport tests exposed the earlier builtin
   parser. A diagnostic run explicitly disables only the early wrapper while
   retaining the factory: **3 failed, 16 passed, 5 deselected**, captured in
   `.local/storage-xml/factory-only-diagnostic.txt`. External entity/malformed
   bodies reached the unguarded builtin and became retried HTTP 500 errors.
   Internal DTD expansion and XML budget enforcement also lacked a guaranteed
   boundary before that first parse, even when later factory rejection occurred.
2. **Appending `register_first`:** an event-emitter probe showed both wildcard
   and exact-operation later registrations still ran after the existing builtin.
   `.local/storage-xml/register-first-order-probe.txt` preserves both observed
   `['builtin', 'guard']` results. The final implementation verifies registration
   and replaces the owned entry instead of relying on this insufficient ordering.

An additional implementation error called `register_first` on `Session`, which
does not expose that method. Its **22 setup errors** were retained in
`.local/storage-xml/failed-wrapper-registration.txt`; it was corrected to use the
owned event-emitter component. Those errors were not reported as passing tests.

## Final verification

```sh
/Users/pie/CargoPulse_Production_Build_Package/.venv/bin/python -m pytest \
  tests/backend/test_storage_xml.py tests/backend/test_api.py -q
```

Result: **49 passed**, comprising **24 new storage/XML cases** and **25 existing
API cases**, with one existing Starlette/httpx deprecation warning.

The new tests instantiate an actual botocore S3 client and replace only its HTTP
transport with recorded in-process responses. They use explicitly fake test
credentials, isolated config paths and network-failing guards. No actual AWS
network or user credentials are read or used. They verify:

- Normal Head/Put operations, original timeout/retry/TLS settings and SSE headers.
- Normal service XML errors, UTF-8/BOM/UTF-16 and namespaced XML, predefined
  entities, parser defaults, JSON behavior and unchanged unowned parsers.
- Internal DTDs, internal entity amplification, external file canary/HTTP entity,
  malformed XML and oversized protocol XML are rejected without raw-body echoes.
- DTD and oversized input are rejected before the builtin detector can execute;
  a test replaces that detector with an immediate failure if reached.
- A raw GetObject blob larger than the XML budget, containing DTD-like and binary
  bytes, still verifies correctly; a test makes any XML-guard call on it fail.
- Normal embedded HTTP 200 S3 errors still become SDK 500 errors with the existing
  two-attempt maximum. Missing expected pinned registration fails closed.
- Rejected protocol body canaries do not appear in SDK DEBUG logs, and
  `verify()` returns `False` on parser errors.

Ruff and `git diff --check` pass. Raw final outputs are retained in
`.local/storage-xml/final-tests.txt` and `.local/storage-xml/ruff.txt`.

## Remaining verification and limits

The SDK class and event-registry hooks are private and pinned. Startup checks
cover the inspected handler shape/order; they cannot prove that a future SDK has
not introduced another earlier parsing path. Preserve dependency pins and repeat
source/transport review before upgrades. Raw-body redaction tests cover rejected
protocol XML, not every possible debug payload emitted by the entire SDK.

Recorded transport tests do not establish real S3 endpoint/IAM policy, actual
TLS certificates, SSE-at-rest behavior, service availability, bucket permissions,
deployment, or airline integration. Those require separately authorized external
integration evidence. No commit, push, root service data, native database or
earlier MFA/cookie worktree was changed. No additional user input is required for
the local patch; the integration lead must re-run checks after applying it.
