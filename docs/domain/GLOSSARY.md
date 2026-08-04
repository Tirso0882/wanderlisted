---
id: domain-glossary
doc_type: domain
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/**, frontend/**, docs/**]
load_when: [terminology, domain, contract]
source_paths: [src/models]
---

# Domain glossary

| Term | Canonical meaning |
|---|---|
| Capability | Stable user-facing planning need such as flights, readiness, or budget; independent of class name. |
| Component | One graph/domain result stored as a `ComponentResult` and optional typed data. |
| Evidence | Provider/domain fact with stable identity and provenance; not model prose. |
| Selection | Explicit validated choice of an evidence ID/rate key/offer ID for downstream truth. |
| Availability | Candidate inventory returned by a provider; never automatically selected. |
| Trip request | Canonical merged `TripRequest` across turns. |
| Request fingerprint | Hash/identifier proving an artifact was built for the current request inputs. |
| Artifact fingerprint | Hash over canonical itinerary inputs used to reject stale delivery. |
| Planning constraint | Grounded readiness restriction handed to downstream planners; not a place recommendation. |
| Trip skeleton | Exact trip dates and city-stay/night allocation, plus selected flight when available. |
| Draft itinerary | Validated selection of canonical hotels and stops before route/schedule compilation. |
| Route plan | Ordered measured legs for selected stops; missing legs remain explicit. |
| Budget breakdown | Deterministic selected/estimated line items, conversions, coverage, totals, and target verdict. |
| Itinerary plan | Deterministically compiled day/time blocks, feasibility, costs, limitations, and fingerprint. |
| Handbook | Deterministic delivery artifact rendered as HTML, Markdown, and JSON from validated typed inputs. |
| EDD | Evaluation-driven development: datasets, deterministic checks, judges, pairwise comparison, and calibration. |
| HITL | Checkpointed human-in-the-loop safety, budget, or final-plan decision. |
| Partial | Usable bounded result with declared missing information; not silent success. |
| Blocked external | Work could not complete because an external provider/infrastructure boundary failed. |
| Stale | Artifact fingerprint no longer matches its current canonical inputs. |
