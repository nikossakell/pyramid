# Deployment on university infrastructure

> Status: outline.

## Prerequisites

- Ubuntu LTS host inside the university network, NVIDIA GPU + drivers, Docker
  with the container toolkit.
- DNS name and a certificate placed in `nginx/ssl/` (gitignored).
- The host must have **swap disabled** -- see `docs/ephemeral-processing.md`.

## Steps

1. `cp .env.example .env` and fill in every secret.
2. `make models` -- downloads the weights (accepting the terms in
   `THIRD_PARTY_LICENSES.md`).
3. Place the EFSA PDFs in `data/efsa_pdfs/`, then `make rag`.
4. `make deploy`.
5. `make check-ephemeral` must pass before any participant is enrolled.

## Rollback

## Backups

Database only. There is nothing else to back up -- no photo ever reaches disk.
