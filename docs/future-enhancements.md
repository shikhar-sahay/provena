# Future enhancements

These are proposals, not implemented features or deployment claims. They should be evaluated against evidence provenance, human oversight, cost, and the project's modular-monolith constraint.

## Explainable analysis

- Bayesian or calibrated confidence models could be explored only with validated data and a clear distinction from today's deterministic weighted scores.
- A case-scoped investigation knowledge graph could expose relationships between people, hosts, files, devices, and events while preserving links to the original artifacts.
- Automated timeline reconstruction could align supported timestamp formats and flag clock uncertainty.
- Cross-case pattern analysis and evidence similarity detection would need explicit workspace authorization, provenance, false-positive measurement, and privacy review.
- spaCy or another NLP library could assist controlled entity extraction if it materially improves recall without weakening source locators or explainability. It is not a current dependency.
- Integration with established digital forensic tools could import structured results with checksums, tool/version metadata, and source references.

## Cloud reliability and security

- S3-backed evidence storage is supported by the code but not selected on the live EC2 instance. A migration would need byte-by-byte reconciliation and coordinated database backup.
- Managed PostgreSQL such as RDS, more memory, automated backups, monitoring, and multi-AZ redundancy could reduce single-instance risk, subject to budget and operational approval.
- CloudFront and private networking are possible later designs but are not part of the current deployment.
- Periodically verify DuckDNS updates, HTTPS redirects, and certificate renewal as ongoing operations.

OCR, deep binary forensics, vector search, RAG, and model training are outside the current implementation. None should be presented as a working Provena feature without tests and evidence traceability.
