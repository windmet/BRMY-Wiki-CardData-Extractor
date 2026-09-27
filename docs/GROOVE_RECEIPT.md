# Calculator export receipt

`python -m toolkit sync groove --output <fresh-output> --cache <cache>` emits
`audit_output/groove_export_receipt_<run_id>.json` only after a successful run.
`--offline` uses verified cached bytes and retains their original retrieval time.
It is not an online freshness check. JSON-only `generate groove` emits no receipt.

Consumers must first require a successful current `output_receipt.json`, then
select its registered `groove_export_receipt_` artifact. Never pick the newest
matching file from an old output folder. Earlier receipts intentionally remain
available for audit, but do not certify a failed retry.

The receipt binds exact export bytes to the downloaded raw hash, decoded hash,
download-associated manifest hash, resource fingerprint and retrieval timestamp.
Before writing, the producer rechecks raw -> decoded bytes -> session source hash,
session JSON hash, and current-run export artifact hash; export Issues block it.
`sourceLastModified` is emitted only from a valid upstream Last-Modified header.
No local paths, URLs, HTTP headers or credentials enter the public receipt.

This is an integrity record from a trusted local producer, not a cryptographic
signature or authentication of arbitrary edited cache metadata. The production
provider and its cache remain inside the trust boundary. Pin the reviewed Toolkit
revision before an unattended consumer relies on these records.

The Calculator consumes it with `npm run data:prepare -- --input <export>
--receipt <receipt>`. That writes an isolated candidate, not the shipped bundle.
No schedule, credentials, automatic commit or publication is configured here.
