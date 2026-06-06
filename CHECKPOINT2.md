# Blood Warriors — Checkpoint 2

Hackathon: AI For Good 2.0  
Region: `ap-south-1` (Mumbai)  
Account: `179503921630`  
Date: 2026-06-06

All five priorities built. Twilio WhatsApp integrated. React frontend built and ready for Amplify.

---

## What's Working

| Priority | Feature | Status |
|---|---|---|
| P1 | Bedrock Haiku personalised WhatsApp messages | ✅ |
| P2 | BotLambda + /webhook + intent classification (YES/NO/MAYBE) | ✅ |
| P3 | EscalationLambda + EventBridge (every 5 min) | ✅ |
| P4 | Dynamic re-ranking via last_contacted_date | ✅ |
| P5 | React + Vite admin dashboard | ✅ (built, Amplify pending) |
| — | Twilio WhatsApp outreach (replaces SNS SMS) | ✅ (pending TWILIO_AUTH_TOKEN) |
| — | AdminLambda GET /admin endpoint | ✅ |

---

## Current Issues / Blockers

### 1. TWILIO_AUTH_TOKEN not set
OutreachLambda and EscalationLambda will fail with HTTP 401 when trying to send WhatsApp messages. Must be set manually.

**Fix:** AWS Console → Lambda → OutreachLambda / EscalationLambda / BotLambda → Configuration → Environment variables → add `TWILIO_AUTH_TOKEN`.

### 2. Twilio WhatsApp sandbox opt-in
The demo phone `+918639448680` must send a join message to the sandbox number before Twilio will deliver outbound messages.

**Fix:** From the demo phone, send `join <keyword>` to `+13613265415` on WhatsApp. Keyword is shown at [Twilio Console → Messaging → Try it out → Send a WhatsApp message](https://console.twilio.com).

### 3. Twilio webhook URL not configured
Twilio sandbox doesn't know where to POST donor replies.

**Fix:** Twilio Console → WhatsApp sandbox → Sandbox settings → "When a message comes in" → set to:
```
POST https://046giqhktg.execute-api.ap-south-1.amazonaws.com/prod/webhook
```

### 4. Amplify not yet connected to GitHub
The React app is built and the `amplify.yml` config is ready, but the Amplify app in AWS console hasn't been created yet.

**Fix:** See "Amplify Setup" section below.

---

## Amplify Setup (manual steps — 5 min)

1. AWS Console → **Amplify** → **New app** → **Host web app**
2. Choose **GitHub** → authorise → select repo `bhadrakorukonda/Blend-Hackathon` → branch `main`
3. Amplify auto-detects `amplify.yml` at repo root — confirm it shows `appRoot: frontend`
4. Click **Save and deploy**

Every push to `main` after that triggers an automatic redeploy (~90s build time).

The `amplify.yml` uses `HashRouter` (URLs like `/#/coordinator`) so no custom redirect rules are needed — every path served by Amplify is `/`, which always returns `index.html`.

---

## Local Development

```bash
cd "H:\Random projects\Blend Hackathon\frontend"

# Dev server (hot reload)
npm run dev
# → http://localhost:5173/#/coordinator

# Preview production build
npm run preview
# → http://localhost:4173/#/coordinator

# Or open dist\index.html directly in a browser — also works
# (asset paths are relative ./assets/... thanks to base: './')
```

---

## API Endpoints

Base URL: `https://046giqhktg.execute-api.ap-south-1.amazonaws.com/prod`

| Method | Path | Lambda | Purpose |
|---|---|---|---|
| POST | /match | MatchingLambda | Find top 5 donors for a patient, trigger outreach |
| POST | /webhook | BotLambda | Twilio posts donor WhatsApp replies |
| GET | /admin | AdminLambda | Dashboard stats (totals, status, responses, demand) |

---

## Lambda Functions

| Name | ARN | Trigger | What it does |
|---|---|---|---|
| MatchingLambda | `arn:aws:lambda:ap-south-1:179503921630:function:MatchingLambda` | API GW POST /match | Scores 6,674 donors, top 5, saves MatchRequest, publishes to SNS |
| OutreachLambda | `arn:aws:lambda:ap-south-1:179503921630:function:OutreachLambda` | SNS BloodMatchTopic | Bedrock Haiku SMS → Twilio WhatsApp to top donor |
| BotLambda | `arn:aws:lambda:ap-south-1:179503921630:function:BotLambda` | API GW POST /webhook | Parses Twilio reply, Bedrock intent classification, updates MatchRequest |
| EscalationLambda | `arn:aws:lambda:ap-south-1:179503921630:function:EscalationLambda` | EventBridge every 5 min | Contacts next donor on timeout or NO reply |
| AdminLambda | `arn:aws:lambda:ap-south-1:179503921630:function:AdminLambda` | API GW GET /admin | Aggregates MatchRequests for dashboard |

---

## Environment Variables per Lambda

### OutreachLambda
| Var | Value |
|---|---|
| TWILIO_ACCOUNT_SID | ACxxxx... (see Twilio console) |
| TWILIO_AUTH_TOKEN | ⚠️ **SET MANUALLY** |
| TWILIO_WHATSAPP_FROM | whatsapp:+13613265415 |
| TWILIO_WHATSAPP_TO | whatsapp:+918639448680 |

### BotLambda
| Var | Value |
|---|---|
| TWILIO_ACCOUNT_SID | ACxxxx... (see Twilio console) |
| TWILIO_AUTH_TOKEN | ⚠️ **SET MANUALLY** |
| TWILIO_WHATSAPP_FROM | whatsapp:+13613265415 |

### EscalationLambda
| Var | Value |
|---|---|
| TWILIO_ACCOUNT_SID | ACxxxx... (see Twilio console) |
| TWILIO_AUTH_TOKEN | ⚠️ **SET MANUALLY** |
| TWILIO_WHATSAPP_FROM | whatsapp:+13613265415 |
| TWILIO_WHATSAPP_TO | whatsapp:+918639448680 |
| ESCALATION_WINDOW_SECONDS | 120 (change to 1800 for production) |

### MatchingLambda
| Var | Value |
|---|---|
| SNS_TOPIC_ARN | arn:aws:sns:ap-south-1:179503921630:BloodMatchTopic |

---

## DynamoDB Tables

| Table | PK | Count | Notes |
|---|---|---|---|
| Donors | user_id (String) | 6,674 | last_contacted_date written by Bot/Escalation |
| Patients | user_id (String) | 84 | Binary-prefixed IDs — use boto3, not shell |
| MatchRequests | request_id (String UUID) | ~20 | top_donors stored as JSON string |
| BotSessions | phone_number (String) | ~1 | One record per phone, overwritten on each reply |

### MatchRequest status flow
```
pending → (donor replies YES) → confirmed
pending → (donor replies NO)  → escalate → EscalationLambda contacts next → pending
pending → (30 min / 2 min demo timeout) → EscalationLambda → pending (next donor)
pending/awaiting/escalate → (all 5 tried) → exhausted
```

---

## Source File Index

### Lambda functions
| File | Deployed as | Notes |
|---|---|---|
| `lambda_matching/lambda_function.py` | MatchingLambda | 5-factor scoring algorithm, unchanged from original |
| `lambda_matching/outreach_lambda.py` | OutreachLambda | Bedrock Haiku + Twilio WhatsApp; uses urllib (no library) |
| `lambda_matching/bot_lambda.py` | BotLambda | Twilio webhook parser, Bedrock intent, strips whatsapp: prefix |
| `lambda_matching/escalation_lambda.py` | EscalationLambda | Timeout/NO escalation, deprioritise_donor(), Twilio send |
| `lambda_matching/admin_lambda.py` | AdminLambda | Scan MatchRequests, return aggregated stats |

### Deploy scripts
| File | What it deploys |
|---|---|
| `lambda_matching/deploy_outreach_bedrock.py` | OutreachLambda + Bedrock IAM policy (P1) |
| `lambda_matching/deploy_bot.py` | BotLambda + /webhook API Gateway route (P2) |
| `lambda_matching/deploy_escalation.py` | EscalationLambda + EventBridge rule (P3) |
| `lambda_matching/deploy_whatsapp.py` | All 3 Lambdas switched to Twilio WhatsApp env vars |
| `lambda_matching/deploy_admin.py` | AdminLambda + GET /admin route |

### Frontend
| File | Purpose |
|---|---|
| `frontend/src/App.jsx` | HashRouter + sticky nav (COORDINATOR / ADMIN tabs) |
| `frontend/src/pages/MatchDashboard.jsx` | Patient selector → match → expandable donor cards with score rings |
| `frontend/src/pages/AdminCenter.jsx` | KPI cards, response rings, demand bars, live request table, 30s auto-refresh |
| `frontend/src/components/ScoreRing.jsx` | SVG ring (green ≥70, amber ≥45, red below) |
| `frontend/src/components/BloodBadge.jsx` | Blood group pill (O=red, A=amber, B=blue, AB=purple) |
| `frontend/src/components/StatusBadge.jsx` | Status pill with per-status colour |
| `frontend/src/api.js` | findDonors() + getAdminStats() against prod API Gateway |
| `frontend/src/data/patients.js` | All 20 patients with correct escaped DynamoDB key strings |
| `frontend/src/index.css` | Dark theme base styles, scan-line overlay, scrollbar |
| `frontend/vite.config.js` | base: './' for relative asset paths |
| `frontend/tailwind.config.js` | Content paths for Tailwind purge |
| `amplify.yml` | Amplify monorepo config (appRoot: frontend, build: npm run build, artifacts: dist) |

### Legacy (superseded by React app, still on S3)
| File | Notes |
|---|---|
| `index.html` | Original S3 frontend — still functional, same /match API |
| `admin.html` | Original S3 admin — still functional, same /admin API |

### Utility / reference
| File | Notes |
|---|---|
| `matcher.py` | Standalone scoring module (logic duplicated inside MatchingLambda) |
| `ingest.py` | One-time data ingestion (already run) |
| `CHECKPOINT.md` | Infrastructure snapshot from end of P4 |
| `lambda_matching/check_api.py` | Debug: lists API Gateway resources and methods |
| `lambda_matching/check_integration.py` | Debug: verifies integration config + direct Lambda invoke |

---

## What's Next

In priority order:

1. **Set TWILIO_AUTH_TOKEN** on all three Lambdas (5 min, AWS Console)
2. **Opt demo phone into WhatsApp sandbox** (send join keyword from +918639448680)
3. **Set Twilio webhook URL** in sandbox settings
4. **Connect Amplify to GitHub** (5 min, AWS Console — see Amplify Setup above)
5. **End-to-end test**: trigger a match from the React frontend, verify WhatsApp message received, reply YES, verify status → confirmed in admin dashboard
6. **For production demo**: change `ESCALATION_WINDOW_SECONDS` from `120` to `1800` on EscalationLambda

---

## Known Technical Debt

- CHECKPOINT.md (infrastructure snapshot) reflects P4 state; env vars section is now outdated (Twilio replaced SNS direct SMS)
- `index.html` and `admin.html` on S3 are legacy — they still work but the React app is the primary frontend going forward
- `check_api.py` and `check_integration.py` in lambda_matching/ are debug scripts, safe to delete after demo
