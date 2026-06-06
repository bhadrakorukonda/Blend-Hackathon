# Blood Warriors — Build Checkpoint

Hackathon: AI For Good 2.0  
Region: ap-south-1 (Mumbai)  
Account: 179503921630  
IAM role (all Lambdas): `BloodWarriorsLambdaRole`  
Priorities 1–4 complete. Priority 5 (admin dashboard) in progress.

---

## Lambda Functions

### MatchingLambda
- **ARN**: `arn:aws:lambda:ap-south-1:179503921630:function:MatchingLambda`
- **Runtime**: python3.10 | **Timeout**: 60s | **Memory**: 512 MB
- **Handler**: `lambda_function.lambda_handler`
- **Source**: `lambda_matching/lambda_function.py`
- **Env vars**:
  - `SNS_TOPIC_ARN` = `arn:aws:sns:ap-south-1:179503921630:BloodMatchTopic`
- **What it does**: Receives `POST /match` from the frontend. Fetches the patient from DynamoDB, scans all Donors, applies 4 hard-gate filters (eligibility, active status, cooldown date, blood compatibility), scores each passing donor on 5 dimensions (distance 30 pts, reliability 25 pts, loyalty 20 pts, donor type 15 pts, recency 10 pts), returns top 5. Saves a MatchRequest record to DynamoDB then publishes to SNS to trigger OutreachLambda.

### OutreachLambda
- **ARN**: `arn:aws:lambda:ap-south-1:179503921630:function:OutreachLambda`
- **Runtime**: python3.12 | **Timeout**: 60s | **Memory**: 256 MB
- **Handler**: `outreach_lambda.lambda_handler`
- **Source**: `lambda_matching/outreach_lambda.py`
- **Trigger**: SNS topic `BloodMatchTopic`
- **Env vars**:
  - `DEMO_PHONE` = `+918639448680`
- **What it does**: Triggered by SNS. Contacts only `top_donors[0]` (the highest-ranked donor). Calls Bedrock Claude 3 Haiku to generate a personalised SMS under 160 chars using the donor's blood group, donor type, donation count, and distance. Falls back to a hardcoded template if Bedrock fails. Sends SMS via SNS direct SMS to DEMO_PHONE. Writes `current_donor_rank=0` and `last_outreach_at` back to the MatchRequest so EscalationLambda can track state.

### BotLambda
- **ARN**: `arn:aws:lambda:ap-south-1:179503921630:function:BotLambda`
- **Runtime**: python3.12 | **Timeout**: 30s | **Memory**: 256 MB
- **Handler**: `bot_lambda.lambda_handler`
- **Source**: `lambda_matching/bot_lambda.py`
- **Trigger**: API Gateway `POST /webhook`
- **Env vars**: none (Bedrock model ID is hardcoded; DEMO_PHONE not needed here)
- **What it does**: Receives Twilio webhook POSTs (URL-encoded form body). Parses `From` and `Body` fields. Calls Bedrock Haiku (temperature=0) to classify the reply as YES / NO / MAYBE. Finds the most recent pending/awaiting MatchRequest and updates its status: YES→`confirmed`, NO→`escalate`, MAYBE→`awaiting`. Upserts a BotSession record keyed by phone number. On NO: reads `current_donor_rank` from the MatchRequest, looks up that donor's `user_id` in `top_donors`, and sets `last_contacted_date=today` in the Donors table (dynamic re-ranking). Returns TwiML XML with a human reply.

### EscalationLambda
- **ARN**: `arn:aws:lambda:ap-south-1:179503921630:function:EscalationLambda`
- **Runtime**: python3.12 | **Timeout**: 60s | **Memory**: 256 MB
- **Handler**: `escalation_lambda.lambda_handler`
- **Source**: `lambda_matching/escalation_lambda.py`
- **Trigger**: EventBridge rule `BloodWarriorsEscalationRule` (every 5 minutes)
- **Env vars**:
  - `DEMO_PHONE` = `+918639448680`
  - `ESCALATION_WINDOW_SECONDS` = `120` (2 min for demo; set to `1800` for production)
- **What it does**: Scans MatchRequests for non-terminal status (pending / awaiting / escalate). For each: checks whether to escalate — immediately if `status=escalate` (donor said NO), or after the window expires for pending/awaiting. Before escalating, calls `deprioritise_donor()` which sets `last_contacted_date=today` on the current donor in the Donors table (dynamic re-ranking). Advances `current_donor_rank` by 1, generates a Bedrock follow-up SMS mentioning it is a follow-up, sends via SNS SMS. Marks `status=exhausted` when all 5 donors are tried.

---

## API Gateway

- **API ID**: `046giqhktg`
- **Stage**: `prod`
- **Base URL**: `https://046giqhktg.execute-api.ap-south-1.amazonaws.com/prod`

| Path | Methods | Lambda | Purpose |
|---|---|---|---|
| `/match` | POST, OPTIONS | MatchingLambda | Frontend triggers donor matching |
| `/webhook` | POST | BotLambda | Twilio posts donor SMS replies |

CORS is enabled on `/match` (OPTIONS method present).

---

## SNS

- **Topic**: `BloodMatchTopic`
- **ARN**: `arn:aws:sns:ap-south-1:179503921630:BloodMatchTopic`
- **Subscription**: OutreachLambda (protocol: lambda)
- **Also used**: OutreachLambda and EscalationLambda publish direct SMS via `sns.publish(PhoneNumber=..., Message=...)`
- **Sandbox**: Demo phone `+918639448680` is verified and receiving SMS

---

## EventBridge

- **Rule**: `BloodWarriorsEscalationRule`
- **ARN**: `arn:aws:events:ap-south-1:179503921630:rule/BloodWarriorsEscalationRule`
- **Schedule**: `rate(5 minutes)` — ENABLED
- **Target**: EscalationLambda

---

## DynamoDB Tables

### Donors
- **PK**: `user_id` (String)
- **Item count**: 6,674
- **Key fields written by the system**: `last_contacted_date` (String, YYYY-MM-DD) — updated by BotLambda on NO intent and by EscalationLambda on timeout/exhausted
- **Key fields read by MatchingLambda**: `eligibility_status`, `user_donation_active_status`, `next_eligible_date`, `blood_group`, `latitude`, `longitude`, `calls_to_donations_ratio`, `donations_till_date`, `donor_type`, `last_contacted_date`, `role`, `gender`, `name`

### Patients
- **PK**: `user_id` (String)
- **Item count**: 84
- **Key fields**: `blood_group`, `bridge_blood_group` (used preferentially), `latitude`, `longitude`
- **Note**: Patient IDs contain raw binary prefix bytes — always access via Python boto3, never shell

### MatchRequests
- **PK**: `request_id` (String, UUID)
- **Item count**: ~15 (grows with each match)
- **Fields**:
  - `request_id` — UUID
  - `patient_id` — FK to Patients
  - `patient_blood_group` — String
  - `status` — `pending` | `awaiting` | `escalate` | `confirmed` | `exhausted`
  - `top_donors` — **JSON string** (not a DynamoDB Map) — list of top 5 scored donor objects
  - `created_at` — ISO timestamp (set by MatchingLambda)
  - `current_donor_rank` — Number (0–4), set by OutreachLambda, advanced by EscalationLambda
  - `last_outreach_at` — ISO timestamp, updated each time an SMS is sent
  - `escalation_count` — Number, incremented by EscalationLambda each hop
  - `donor_response` — Map `{phone, intent, message}`, set by BotLambda
  - `responded_at` — ISO timestamp, set by BotLambda
- **Critical**: `top_donors` is always `json.dumps(list)` / `json.loads(str)` — never stored as a DynamoDB Map

### BotSessions
- **PK**: `phone_number` (String)
- **Item count**: 0 (upserted on each reply — one record per phone, overwritten)
- **Fields**:
  - `phone_number` — donor phone (DEMO_PHONE in hackathon)
  - `request_id` — FK to MatchRequests
  - `last_message` — raw reply text
  - `intent` — `YES` | `NO` | `MAYBE`
  - `message_sid` — Twilio MessageSid
  - `updated_at` — ISO timestamp

---

## S3 Frontend

- **Bucket**: `blood-warriors-ui`
- **URL**: `http://s3-ap-south-1.amazonaws.com/blood-warriors-ui/index.html`
- **Source**: `index.html`
- **What it does**: Static single-page app. Patient dropdown (20 hardcoded patients with binary user_id values). On submit, POSTs to `/match`. Displays top 5 donors as expandable cards with SVG score rings. Shows blood group badges, donor stats, and an "SMS sent" pill.

---

## Source Files

| File | Purpose |
|---|---|
| `lambda_matching/lambda_function.py` | MatchingLambda handler — scoring, gating, SNS publish |
| `lambda_matching/outreach_lambda.py` | OutreachLambda — Bedrock SMS to top donor, writes outreach metadata |
| `lambda_matching/bot_lambda.py` | BotLambda — Twilio webhook, Bedrock intent classification, re-ranking on NO |
| `lambda_matching/escalation_lambda.py` | EscalationLambda — timeout/NO escalation, re-ranking on timeout |
| `lambda_matching/deploy_outreach_bedrock.py` | Deploys OutreachLambda + attaches Bedrock/Marketplace IAM policy |
| `lambda_matching/deploy_bot.py` | Deploys BotLambda + wires /webhook on API Gateway |
| `lambda_matching/deploy_escalation.py` | Deploys EscalationLambda + OutreachLambda update + EventBridge rule |
| `matcher.py` | Standalone scoring module (used locally; logic duplicated in lambda_function.py) |
| `ingest.py` | One-time data ingestion script |
| `index.html` | S3 frontend |

---

## Bedrock

- **Model**: `anthropic.claude-3-haiku-20240307-v1:0`
- **Used by**: OutreachLambda (initial personalised SMS), BotLambda (intent classification), EscalationLambda (follow-up personalised SMS)
- **IAM**: `BloodWarriorsBedrockPolicy` inline policy on `BloodWarriorsLambdaRole` grants `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`, `aws-marketplace:ViewSubscriptions`, `aws-marketplace:Subscribe`, `aws-marketplace:Unsubscribe`
- **Note**: Claude 3.5 Sonnet v2 (`anthropic.claude-3-5-sonnet-20241022-v2:0`) requires cross-region inference profile — not enabled in this account. Haiku works on-demand.

---

## Scoring Algorithm (matcher.py / lambda_function.py)

| Dimension | Max pts | Logic |
|---|---|---|
| Distance | 30 | Full at ≤50 km, zero at ≥500 km, linear between |
| Reliability | 25 | Lower `calls_to_donations_ratio` = higher score; clamped at ratio 5 |
| Loyalty | 20 | `donations_till_date / 12`, capped at 1.0 |
| Donor type | 15 | Regular Donor=15, One-Time=5, other=8 |
| Recency | 10 | 10 if not contacted in last 7 days, 0 if contacted within 7 days |

Hard gates (all must pass): `eligibility_status=eligible`, `user_donation_active_status=active`, `next_eligible_date` not in future, blood group compatible with patient.

---

## Dynamic Re-Ranking (Priority 4)

When a donor does not respond (NO reply or timeout), `last_contacted_date` is set to today in the Donors table:
- **BotLambda**: fires on `intent=NO`
- **EscalationLambda**: fires before every escalation hop (timeout or NO) via `deprioritise_donor()`

Effect: `recency_score()` returns 0 pts for 7 days. Donor remains in the pool and fully recovers after the window. No permanent penalty, no removal.

---

## State Machine (MatchRequest.status)

```
pending   — outreach sent, awaiting reply
awaiting  — donor replied MAYBE
escalate  — donor replied NO (BotLambda), triggers immediate escalation
confirmed — donor replied YES, request fulfilled
exhausted — all 5 donors tried with no YES
```
