# VetConnect backend productionization checklist

## Audit and baseline
- [x] Review the existing backend modules, dependencies, and current API behavior.
- [x] Record compatibility constraints and the target local development workflow. The prototype uses FastAPI + SQLAlchemy + SQLite, creates tables at import time, hard-codes JWT secrets, lacks dependency metadata, and allows invalid request-state transitions.

## Configuration and database
- [x] Add environment-based settings with safe production defaults.
- [x] Make database access PostgreSQL-ready while retaining SQLite for local development.
- [x] Add migration tooling and an initial schema migration.

## Security and domain rules
- [x] Harden password hashing and JWT configuration.
- [x] Enforce role and ownership checks on pets and service requests.
- [x] Validate service-request lifecycle transitions and veterinarian verification/availability.
- [x] Add CORS, request validation, and structured error handling.

## Quality and delivery
- [x] Add automated API tests for authentication, pet ownership, matching, and lifecycle transitions. The suite passes 5 tests.
- [x] Run checks and document environment variables, migrations, and deployment steps. Alembic upgrade/current validation passes.
- [x] Package the productionized backend and deliver the updated archive: `/home/ubuntu/vet_connect_production.tar.gz`.


# Next milestone: verification, staging, and live reference integration

## Verification workflow
- [x] Define administrator identity and verification audit fields.
- [x] Add protected administrator endpoints to list pending vets and review verification.
- [x] Add verification tests and prevent public administrator signup.

## Staging and operations
- [x] Add Dockerfile and PostgreSQL-backed staging compose configuration.
- [x] Add concise structured request logging; production error observability remains deployment-specific.
- [x] Document required secrets, migrations, health checks, and CORS origins.

## Live API reference
- [x] Add a configurable backend base URL and bearer token to the API reference website.
- [x] Add live request execution with clear sandbox/live status and safe error handling.
- [ ] Verify the integrated request flow on desktop and mobile against a deployed backend.


# Next milestone: staging deployment and operator handoff

## Deployment target
- [ ] Confirm whether staging will use Manus WebDev backend hosting, an attached persistent environment, or a third-party cloud account.
- [ ] Confirm the staging API hostname and PostgreSQL provider.
- [ ] Collect only the required deployment values: database URL, JWT secret, CORS origin, and administrator bootstrap method.

## Staging release
- [x] Prepare release configuration and verify the migration startup path. Docker was unavailable, so staging uses the portable SQLite fallback.
- [x] Start the local staging API on `127.0.0.1:8001`.
- [x] Run health, migration, authentication, authorization, pet, request, availability, and acceptance checks; the smoke flow passed.

## Integration and handoff
- [x] Set the API reference default base URL to the temporary local staging tunnel and enable live mode by default for this checkpoint.
- [x] Execute client and veterinarian workflows end to end against local staging; administrator verification is covered by the backend test suite.
- [ ] Document operator access, backups, rollback, and production promotion steps.
