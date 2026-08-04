# External tool scope

Read `docs/architecture/DATA_AND_INTEGRATIONS.md`, `docs/rules/selection-and-pricing.md`, and the matching feature pack.

Tools own provider authentication, request construction, explicit timeouts, response normalization, redaction, and typed/classified failures. They do not decide itinerary truth outside returned evidence.

Keep credentials in environment variables. Never log secrets or unredacted signed URLs. Preserve stable provider IDs, currencies, price scope/basis, timestamps, URLs, and selection status needed downstream. Network retries must be bounded and safe for the operation.

Default tests mock HTTP. Mark live checks as integration and run them only with explicit approval, disclosed call count, and configured test credentials.
