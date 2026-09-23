# Layer 101 — Production provenance attestation

Layer 100 proved deterministic runtime contracts but intentionally did not claim
that a particular Git commit was the code running in Railway.

Layer 101 closes that gap with a privacy-safe provenance receipt built from
Railway's own runtime source metadata.

## Receipt fields

The receipt contains only non-secret deployment identity:

- GitHub repository owner/name;
- branch;
- full deployed commit SHA;
- Railway project name;
- Railway service name;
- Railway environment name;
- expected production identity;
- a self-hash of the receipt.

It does **not** enumerate the environment or include API keys, Supabase
credentials, tokens, URLs containing credentials, or arbitrary variables.

## Production identity contract

A receipt may claim `verified_production` only when:

- repository = `doug-dotcom/Project-L-Modular`;
- branch = `main`;
- service = `Project-L-Modular`;
- environment = `production`;
- commit SHA is a valid 40-character Git SHA.

A self-hash alone is not enough. Verification independently rechecks the expected
production identity so a rehashed receipt with a changed service, branch or
environment still fails.

## Runtime surfaces

Layer 101 adds the provenance receipt to:

- `/health`;
- `/cognition/status`;
- `GET /cognition/release-provenance`.

The cognition endpoint also returns an independent verification result.

## Claim boundary

A verified provenance receipt establishes which source identity the running
container reports. It does not establish:

- that the commit is correct or high quality;
- that Railway health is good;
- answer quality;
- private-memory recall quality;
- phone UX;
- human acceptance.

Those remain separate checks.

## External confirmation

For a live release, compare the receipt's `commit_sha` with Railway's deployment
metadata for the active Project-L-Modular service. Agreement between the
application receipt and the deployment platform closes the "merged versus
actually running" ambiguity.
