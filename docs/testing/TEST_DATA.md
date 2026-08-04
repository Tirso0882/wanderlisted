---
id: testing-test-data
doc_type: testing
status: active
authority: normative
owners: [travel-platform]
applies_to: [tests/**, edd/**, src/evaluation/**]
load_when: [test-data, fixtures, datasets, privacy]
source_paths: [tests, edd, src/evaluation]
---

# Test data

## Classes

- Inline/unit fixtures: minimal deterministic payloads, no secrets or network.
- Provider fixtures: sanitized representative responses with stable fake IDs.
- Golden/EDD cases: versioned inputs, expected behavior/labels, scenario metadata.
- Cached trajectories: ignored local artifacts keyed by dataset/config/source fingerprint.
- Human labels: versioned, reviewer-owned calibration truth without personal data.

## Requirements

Use synthetic or safely sanitized traveler data. Never commit credentials, signed URLs, raw personal conversations, or provider payloads whose terms prohibit storage. Preserve currencies, date/stay scopes, IDs, and edge conditions needed for behavior. Avoid timestamps/randomness unless fixed.

Every dataset states owner, version/fingerprint mechanism, truth source, intended metrics, inapplicable handling, and external-failure classification. A changed prompt/model/tool/source invalidates a trajectory cache when included in its fingerprint.

## Promotion workflow

Reproduce a failure, remove sensitive data, define expected owner behavior, add the smallest deterministic case, then add a broader EDD case only when semantic/trajectory evidence is required.
