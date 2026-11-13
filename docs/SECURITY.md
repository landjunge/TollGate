# Security notes — Tollgate Core

**Stand:** 2026-08-12  
**Scope:** self-hosted Core (one operator). Not a formal pen-test report.

---

## Threat model (short)

| Trust | Assumption |
|-------|------------|
| Local desk | Open mode + `HOST=127.0.0.1` — attacker is on the machine |
| Shared host | Must use consumers auth; never open mode on `0.0.0.0` |
| Public bind | `HOST=0.0.0.0` + open mode is **refused** at serve unless `TOLLGATE_ALLOW_OPEN_PUBLIC=1` |
| Agents | Untrusted input; Tollgate admits/denies *before* spend |

---

## Checklist (operator)

- [ ] **Bind:** default `HOST=127.0.0.1`. Public bind only behind proxy + auth.
- [ ] **Open mode:** no `consumers.json` → any label is a lane. Fine on localhost only.
- [ ] **Public + open:** process **exits** (`open_public_bind`). Override: `TOLLGATE_ALLOW_OPEN_PUBLIC=1`.
- [ ] **Auth mode:** `User/consumers.json` or `TOLLGATE_REQUIRE_AUTH=1`; admin for freeze/config.
- [ ] **Secrets:** `User/Key.txt` / env only — never in audit UI payloads as raw keys.
- [ ] **Metrics:** not public unless `TOLLGATE_METRICS_PUBLIC=1` (explicit).
- [ ] **Dashboard:** unauthenticated HTML; gate at network layer if exposed.
- [ ] **Snapshot export:** keys off by default (`--include-secrets` opt-in).
- [ ] **Freeze fail-closed:** admit denies if freeze subsystem errors.
- [ ] **Ledger fail-closed:** usage write failure → deny (tested).
- [ ] **Webhooks:** only send to URLs you configure; treat as sensitive sinks.
- [ ] **CORS:** browser apps should not hit admin ports cross-origin without intent.

## Code behaviors to keep

| Area | Behavior |
|------|----------|
| Freeze | Fail-closed on check error |
| Admit | Hard deny with structured `blocked` card |
| OpenAI errors | Human message preferred; no secret echo |
| Doctor | Surfaces open mode + high-risk uncapped providers |
| Production readiness | `tollgate doctor` → `production_readiness` score |

## Before non-local users

1. Run `tollgate doctor` — note production readiness %  
2. Enable consumers auth if multi-host  
3. Confirm freeze + loop deny in Control Room  
4. `tollgate snapshot export` backup path known  
5. Pass [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)

## Reporting

No public bounty program. Prefer private disclosure via GitHub security advisory on `landjunge/TollGate` when available.

---

*Update this file when a dedicated security pass is completed (date + findings).*
