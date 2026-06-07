# Blood Warriors — Autonomous AI Donor Matching Platform

### Patient to confirmed donor. Zero humans in the loop.

![AWS](https://img.shields.io/badge/AWS-Lambda%20%7C%20DynamoDB%20%7C%20Bedrock-FF9900?logo=amazonaws&logoColor=white)
![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=black)
![Python](https://img.shields.io/badge/Python-3.10%2F3.12-3776AB?logo=python&logoColor=white)
![Twilio](https://img.shields.io/badge/Twilio-WhatsApp%20API-F22F46?logo=twilio&logoColor=white)
![Bedrock](https://img.shields.io/badge/Amazon%20Bedrock-Claude%203%20Haiku-purple)

---

## 1. Problem Statement

India has **100,000+ Thalassemia patients**, each requiring **500–700 blood transfusions over a lifetime**. Every transfusion depends on finding a compatible, eligible, willing donor — fast. Today this entire chain (finding a donor, contacting them, following up, escalating when they decline, recording the outcome) is done **manually** by NGO coordinators over phone calls and WhatsApp, one patient at a time. It does not scale, and it burns out the volunteers who run it.

## 2. Solution Overview

Blood Warriors is an **end-to-end autonomous pipeline** that takes a blood request from "patient needs blood" to "donor confirmed and a coordinator notified" with no manual matching, messaging, or follow-up:

1. A patient (or coordinator) submits a request.
2. A Lambda scores the entire donor pool against the patient on five weighted factors and ranks the top 5.
3. The top-ranked donor is contacted over WhatsApp with an AI-personalized message (Amazon Bedrock / Claude 3 Haiku).
4. The donor's free-text WhatsApp reply — in **any of 9 Indian languages** — is classified by an LLM into one of 6 intents and answered conversationally in the same language.
5. If the donor doesn't respond in time or declines, the system **automatically escalates to the next-ranked donor** — no human re-dials anyone.
6. Once a donor confirms, a coordinator is notified over WhatsApp, a 2-hour donation follow-up is scheduled automatically, and the outcome (donated / unable) feeds back into the donor's profile for future matching.

## 3. Architecture

```
 FLOW A — Outbound matching & outreach
 ─────────────────────────────────────
                                         ┌───────────────┐
   Coordinator / Patient Portal  ──POST──▶  API Gateway   │
   (React, /coordinator /patient)         │  /match /enroll│
                                          └───────┬───────┘
                                                  │ invokes
                                                  ▼
                                         ┌──────────────────┐
                                         │  MatchingLambda   │  scores + ranks donor pool,
                                         │ (lambda_function) │  writes MatchRequest, fires SNS
                                         └────────┬──────────┘
                                                  │ publish
                                                  ▼
                                         ┌──────────────────┐
                                         │   SNS Topic       │   BloodMatchTopic
                                         │ (NewMatchRequest /│
                                         │ LowDonorQuality)  │
                                         └────────┬──────────┘
                                                  │ triggers
                                                  ▼
                                         ┌──────────────────┐       ┌────────────────┐
                                         │  OutreachLambda   │──────▶│ Twilio WhatsApp │──▶ Donor's phone
                                         │ (Bedrock Haiku    │       │      API        │
                                         │  personalization) │       └────────────────┘
                                         └──────────────────┘


 FLOW B — Inbound donor conversation & confirmation
 ──────────────────────────────────────────────────
   Donor's WhatsApp reply
            │
            ▼
   ┌────────────────┐   webhook   ┌───────────────┐    ┌────────────────────┐
   │ Twilio WhatsApp │───POST────▶│  API Gateway   │───▶│     BotLambda       │
   │      API        │            │   /webhook     │    │ (bot_lambda.py)     │
   └────────────────┘            └───────────────┘    └─────────┬──────────┘
                                                                  │ classify intent +
                                                                  │ generate reply
                                                                  ▼
                                                        ┌──────────────────────┐
                                                        │   Amazon Bedrock      │
                                                        │  Claude 3 Haiku       │
                                                        │ (intent + language +  │
                                                        │  conversational reply)│
                                                        └─────────┬────────────┘
                                                                  │ updates
                                                                  ▼
                                                        ┌──────────────────────┐
                                                        │      DynamoDB         │
                                                        │ MatchRequests,        │
                                                        │ BotSessions, Donors   │
                                                        └──────────────────────┘

   Background loops (EventBridge):
     • EscalationLambda  — every 5 min, times out non-responders, advances to next-ranked donor
     • FollowUpLambda    — fired 2h after a YES via EventBridge Scheduler, asks "did you donate?"
```

## 4. Live Links

| Surface | URL |
|---|---|
| Frontend (Amplify) | https://main.d21n0ooktmzpy5.amplifyapp.com |
| Coordinator console | [`/#/coordinator`](https://main.d21n0ooktmzpy5.amplifyapp.com/#/coordinator) |
| Patient self-enrollment | [`/#/patient`](https://main.d21n0ooktmzpy5.amplifyapp.com/#/patient) |
| Donor self-service portal | [`/#/donor`](https://main.d21n0ooktmzpy5.amplifyapp.com/#/donor) |
| Admin / analytics dashboard | [`/#/admin`](https://main.d21n0ooktmzpy5.amplifyapp.com/#/admin) |

## 5. Tech Stack

**AWS**
- **Lambda** (Python 3.10 / 3.12) — 7 functions, see below
- **API Gateway** (REST, `046giqhktg`) — `/match`, `/enroll`, `/webhook`, `/admin` with CORS
- **DynamoDB** — `Donors`, `Patients`, `MatchRequests`, `BotSessions`
- **SNS** — `BloodMatchTopic`, decouples matching from outreach, carries `NewMatchRequest` and `LowDonorQualityAlert` messages
- **Amazon Bedrock** — `anthropic.claude-3-haiku-20240307-v1:0` for message generation, intent classification, language detection
- **EventBridge Scheduler** — one-shot 2-hour donation follow-up reminders, auto-deletes after firing
- **EventBridge Rules** — recurring 5-minute trigger for `EscalationLambda`
- **IAM** — single `BloodWarriorsLambdaRole` shared across all functions
- **Amplify** — hosts and builds the React frontend from `frontend/` (monorepo `appRoot`)

**Third-party**
- **Twilio WhatsApp Business API** — all donor and coordinator messaging (raw `urllib` REST calls, no SDK)
- **React 18 + React Router 6 (HashRouter) + Vite 6 + Tailwind CSS 3** — frontend

## 6. Matching Algorithm

Implemented in [`lambda_matching/lambda_function.py`](lambda_matching/lambda_function.py). Every eligible donor is scored out of **100** across five weighted factors:

| Factor | Max points | Formula |
|---|---|---|
| **Distance** | 30 | Haversine distance; full 30 pts at ≤ 50 km, linearly decays to 0 at ≥ 500 km |
| **Reliability** | 25 | `25 × (1 − min(calls_to_donations_ratio, 5) / 5)` — fewer calls needed per donation scores higher |
| **Loyalty** | 20 | `20 × min(donations_till_date / 12, 1)` — caps out at 12 lifetime donations |
| **Donor type** | 15 | Regular Donor = 15, One-Time Donor = 5, anything else = 8 |
| **Recency** | 10 | 0 pts if contacted within the last 7 days, else 10 — this is what drives dynamic re-ranking |

**Hard gates** — a donor is excluded entirely (not just scored low) unless **all** of the following hold:
- `eligibility_status == 'eligible'`
- `user_donation_active_status == 'active'`
- `next_eligible_date` is empty or in the past
- Donor's `blood_group` is compatible with the patient's blood group per the standard 8×8 ABO/Rh compatibility matrix (`BLOOD_COMPAT`)

The donor pool is scanned, gated, scored, and sorted; the **top 5** are persisted to `MatchRequests.top_donors` (as a JSON string) and published to SNS for outreach.

**Low-quality alert** — if the top-ranked donor's score is below `QUALITY_THRESHOLD` (env var, default **40**), a separate `LowDonorQualityAlert` SNS message fires with the patient's location, evaluated donor count, and top score, flagging the request for manual intervention.

## 7. Lambda Functions

| Lambda | File | Trigger | Inputs | Outputs |
|---|---|---|---|---|
| **MatchingLambda** | [`lambda_matching/lambda_function.py`](lambda_matching/lambda_function.py) | API Gateway `POST /match` | `{ patient_id }` | Scores & ranks donor pool, writes `MatchRequests` item, publishes `NewMatchRequest` (and optionally `LowDonorQualityAlert`) to SNS, returns top 5 donors + scores |
| **OutreachLambda** | [`lambda_matching/outreach_lambda.py`](lambda_matching/outreach_lambda.py) | SNS (`BloodMatchTopic`) | SNS message `{ request_id, patient_id, patient_blood_group, top_donors }` | Generates a personalized WhatsApp message via Bedrock for the #1-ranked donor (fallback template on failure), sends via Twilio, stamps `current_donor_rank=0` and `last_outreach_at` on the `MatchRequests` item |
| **BotLambda** | [`lambda_matching/bot_lambda.py`](lambda_matching/bot_lambda.py) | API Gateway `POST /webhook` (Twilio) | Twilio webhook form-body (`From`, `Body`, `MessageSid`) | Classifies intent + language + decline reason via Bedrock, generates a context-aware reply in the donor's language, updates `MatchRequests` status, upserts `BotSessions` conversation history, notifies the coordinator and schedules a follow-up on `YES`, returns TwiML |
| **EscalationLambda** | [`lambda_matching/escalation_lambda.py`](lambda_matching/escalation_lambda.py) | EventBridge rule, every 5 minutes | — (scans `MatchRequests`) | Times out requests that have been `pending`/`awaiting` past `ESCALATION_WINDOW_SECONDS` (default 1800s) or that the donor explicitly declined (`escalate`); deprioritizes the unresponsive donor (`last_contacted_date = today`), advances `current_donor_rank`, sends a fresh AI-personalized WhatsApp to the next-ranked donor, or marks the request `exhausted` if the pool runs out |
| **FollowUpLambda** | [`lambda_matching/followup_lambda.py`](lambda_matching/followup_lambda.py) | EventBridge Scheduler one-shot rule (created by BotLambda 2h after a `YES`) | `{ phone, request_id, donor_name }` | Sends a "did you complete your donation? Reply DONATED or UNABLE" WhatsApp message, stamps `followup_sent_at` on the `MatchRequests` item — the actual reply is then handled by BotLambda |
| **AdminLambda** | [`lambda_matching/admin_lambda.py`](lambda_matching/admin_lambda.py) | API Gateway `GET /admin[?phone=]` | Optional `phone` query param | With `phone`: looks up a donor's profile (reliability %, loyalty tier, eligibility). Without: scans all `MatchRequests` and returns aggregate stats — status counts, blood-group demand, intent breakdown, decline-reason breakdown, hesitation breakdown, human-escalation queue, donation-confirmation outcomes |
| **EnrollLambda** | [`enroll_lambda/enroll_lambda.py`](enroll_lambda/enroll_lambda.py) | API Gateway `POST /enroll` | `{ name, blood_group, latitude, longitude, phone, urgency, city?, age? }` | Validates blood group / urgency / coordinates, writes a new `Patients` item and a `PENDING` `MatchRequests` placeholder, returns `patient_id` |

## 8. Frontend Routes

`HashRouter`-based SPA in [`frontend/`](frontend/), built with React + Vite + Tailwind, deployed via AWS Amplify.

| Route | Page | Purpose |
|---|---|---|
| `/` | redirect | → `/coordinator` |
| `/coordinator` | [`MatchDashboard`](frontend/src/pages/MatchDashboard.jsx) | Coordinator picks one of 20 demo patients, runs `findDonors`, watches a live "scanning donor pool" animation, then sees the ranked top-5 donors with full score breakdowns |
| `/admin` | [`AdminCenter`](frontend/src/pages/AdminCenter.jsx) | Analytics dashboard: success rate, status/intent counts, decline-reason bar chart, hesitation breakdown, human-escalation queue, donation-confirmation outcomes — all from `getAdminStats()` |
| `/patient` | [`PatientPortal`](frontend/src/pages/PatientPortal.jsx) | Self-service blood request form (name, blood group, urgency, phone, geolocation via browser API) that calls `EnrollLambda` directly |
| `/donor` | [`DonorPortal`](frontend/src/pages/DonorPortal.jsx) | Self-service donor lookup by phone number — shows blood group, reliability score, loyalty tier, donation history, eligibility status |

## 9. DynamoDB Schema

All tables live in `ap-south-1`. Key fields observed in the Lambda code:

**`Donors`** (PK: `user_id`)
`name`, `phone` / `mobile`, `blood_group`, `gender`, `city`, `latitude`, `longitude`, `donor_type` (`Regular Donor` / `One-Time Donor` / other), `donations_till_date`, `confirmed_donations`, `calls_to_donations_ratio`, `eligibility_status`, `user_donation_active_status`, `next_eligible_date`, `last_donation_date`, `last_contacted_date`, `role`

**`Patients`** (PK: `user_id`)
`name`, `phone`, `blood_group` / `bridge_blood_group`, `latitude`, `longitude`, `urgency` (`CRITICAL`/`HIGH`/`NORMAL`), `city`, `age`, `created_at`

**`MatchRequests`** (PK: `request_id`)
`patient_id`, `patient_blood_group`, `status` (`pending` → `awaiting`/`escalate` → `confirmed`/`exhausted`/`cancelled`), `top_donors` (JSON string of the ranked top-5 array), `current_donor_rank`, `created_at`, `last_outreach_at`, `responded_at`, `donor_response` (map: `phone`, `intent`, `message`, `decline_reason`), `decline_reason`, `escalation_count`, `human_escalation_flag`, `human_escalation_reason`, `donation_confirmed`, `donation_date`, `followup_sent_at`

**`BotSessions`** (PK: `phone_number`)
`request_id`, `last_message`, `intent`, `language`, `decline_reason`, `message_sid`, `updated_at`, `conversation_history` (JSON string array of `{ role, message, intent, language, decline_reason, timestamp }`)

## 10. Bot Intent Classes

`BotLambda` makes a single Bedrock call that returns `<INTENT> <LANG> <DECLINE_REASON>` in one line. **6 intent classes** drive the conversation state machine:

| Intent | Meaning | `MatchRequests.status` |
|---|---|---|
| `YES` | Donor agrees / confirms availability | `confirmed` (→ notifies coordinator, schedules 2h follow-up) |
| `NO` | Donor declines | `escalate` (→ immediate escalation to next donor) |
| `MAYBE` | Uncertain / conditional / no clear signal | `awaiting` (→ AI-generated encouraging reply) |
| `HESITANT_LOGISTICS` | Willing, but blocked by a practical barrier (transport, location, timing) | `awaiting` (→ AI reply with hospital address & transport offer, or `LOGISTICS_FALLBACK`) |
| `HESITANT_AWARE` | Unsure what donation involves (safety, process, eligibility, pain) | `awaiting` (→ AI reassurance reply, or `AWARE_FALLBACK`) |
| `FLAGGED_HUMAN` | Abuse, hostility, distress, mental-health signal, medical emergency, or too ambiguous | `awaiting` + `human_escalation_flag=True` (frozen for human review, no further automation) |

Two additional intents (`DONATED`, `UNABLE`) are recognized **only** in response to the post-confirmation follow-up question, and both resolve to `confirmed` while recording `donation_confirmed`.

**Decline taxonomy** (only populated when intent = `NO`) — **5 categories**: `TRANSPORT`, `TIMING`, `HEALTH`, `AWARENESS`, `OTHER`. Surfaced in the admin "Why donors decline" bar chart.

**Language support — 9 languages**: English (`en`), Hindi (`hi`), Telugu (`te`), Tamil (`ta`), Kannada (`kn`), Malayalam (`ml`), Bengali (`bn`), Marathi (`mr`), Gujarati (`gu`), with an `other` fallback. The classifier detects the language and `generate_conversational_reply` responds in that same language.

## 11. Demo Instructions

**Prerequisites**: open the [live frontend](https://main.d21n0ooktmzpy5.amplifyapp.com) — no local setup required.

### Donor self-service portal (`/#/donor`)
Look up a seeded demo donor profile by phone number:
```
9100000001
9100000002
9100000003
```
Each returns a full profile card — blood group, city, reliability %, loyalty tier (Bronze/Silver/Gold), donations to date, eligibility, and next-eligible date.

### Patient enrollment flow (`/#/patient`)
1. Fill in name, blood group, phone, urgency (`CRITICAL`/`HIGH`/`NORMAL`).
2. Click **USE MY LOCATION** to populate latitude/longitude from the browser geolocation API (or type coordinates manually).
3. Submit — `EnrollLambda` validates the payload, writes a new `Patients` record and a `PENDING` `MatchRequests` placeholder, and returns a `patient_id`.

### Coordinator match flow (`/#/coordinator`)
1. Select one of the 20 seeded demo patients from the dropdown (each has a real Hyderabad-area `patient_id` and blood group).
2. Click **INITIATE MATCH SEQUENCE** — watch the live scan animation (compatibility check → eligibility gate → distance scoring → reliability analysis → AI ranking).
3. `MatchingLambda` scores and gates the entire ~7,033-donor pool, persists the request, and fires SNS — `OutreachLambda` then sends a Bedrock-personalized WhatsApp to donor #1.
4. The dashboard renders the #1 match as a hero card (full score breakdown) plus the remaining top-5 as expandable rows.
5. From here the pipeline runs autonomously: donor replies are classified and answered by `BotLambda`, non-responders are escalated by `EscalationLambda` every 5 minutes, and confirmations trigger coordinator notification + a 2-hour donation follow-up.

### Admin dashboard (`/#/admin`)
Live aggregate view of every `MatchRequests` item: success rate, status distribution, blood-group demand, intent breakdown, decline-reason chart, hesitation breakdown, the human-escalation review queue, and donation-confirmation outcomes.

## 12. Key Technical Decisions

- **`Decimal` for DynamoDB floats** — DynamoDB's `boto3` resource API rejects native Python `float`; all coordinates and numeric fields are stored/read as `Decimal` and converted with a recursive `sanitize()` helper before JSON serialization (`lambda_function.py`).
- **`\x01`-prefixed patient IDs** — the seeded dataset's `user_id` keys contain literal prefix bytes (e.g. `\x01b2c2146...`). The frontend's demo patient list ([`data/patients.js`](frontend/src/data/patients.js)) stores these as escaped JS strings (`'\\x01...'`) so they round-trip correctly through `JSON.stringify` to the API — and any local inspection of these keys must go through `boto3`, never a shell, to avoid byte-mangling.
- **`top_donors` stored as a `json.dumps()` string, not a DynamoDB Map/List** — keeps the ranked donor snapshot immutable and cheap to re-parse across `OutreachLambda`, `BotLambda`, and `EscalationLambda` without dealing with nested `Decimal`/type marshalling on every read.
- **`HashRouter`** — the SPA uses hash-based routing (`/#/coordinator`, `/#/patient`, …) so client-side routes resolve correctly when served as a static bundle from Amplify/S3 without server-side rewrite rules.
- **`QUALITY_THRESHOLD` env var** — the "no good donors nearby" alert threshold (default `40`/100) is externalized so it can be tuned per deployment/region without a code change; crossing it fires a distinct `LowDonorQualityAlert` SNS message carrying the patient's location and donor-pool evaluation stats for manual triage.
- **Single Bedrock call for intent + language + decline reason** — `classify_intent_and_language` returns all three signals in one structured `<INTENT> <LANG> <DECLINE_REASON>` line, halving Bedrock latency/cost versus separate classification calls, with strict whitelisted-token parsing to guard against malformed model output.
- **Never permanently penalize donors** — `NO`/`UNABLE`/timeout responses only set `last_contacted_date = today`, which zeroes the recency-score component for 7 days (`recency_score()`); the donor remains in the eligible pool and naturally re-enters rotation. This was an explicit hackathon judging constraint: automation must never shrink the donor pool.

## 13. Hackathon Context

Built solo in **48 hours** for **AI For Good 2.0**, in partnership with the **Blood Warriors Foundation** (Hyderabad), an NGO that coordinates voluntary blood donation for Thalassemia patients across India. The dataset reflects their real donor categories — Emergency Donor, Bridge Donor, Guest, Volunteer — at Hyderabad-area scale (~7,000 donor records, 8 blood groups), matched against real GPS coordinates with synthetic phone numbers routed through a Twilio WhatsApp sandbox for the demo.
