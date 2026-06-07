# Blood Warriors — AI-Enabled Donor Matching Platform

> Autonomous blood donor matching and WhatsApp outreach for Thalassemia patients across India.

## Live Demo
**Frontend:** https://main.d21n0ooktmzpy5.amplifyapp.com

## The Problem
100,000+ Thalassemia patients need up to 700 blood transfusions in a lifetime. Today, matching donors to patients is entirely manual — coordinators make 10+ calls per request, taking 20–40 minutes. Blood Warriors has 7,000+ donors across Hyderabad. The problem is not supply. The problem is coordination.

## Our Solution
An autonomous AI network that finds the right donor and contacts them via personalised WhatsApp — in under 5 seconds. No human in the loop.

## How It Works
1. Coordinator selects a patient → system scores all 7,033 donors using a 5-factor trust model
2. Top 5 donors contacted instantly via AI-personalised WhatsApp messages (Bedrock Haiku)
3. Donor replies in any Indian language → bot classifies intent, detects hesitation, fights for YES
4. No response in 30 min → EscalationLambda auto-contacts next donor
5. System learns from every decline — diagnosing why donors say no, not just that they did

## AI Layer
- **Outreach generation** — Bedrock Haiku writes a personalised message per donor
- **Intent classification** — YES / NO / MAYBE / HESITANT_LOGISTICS / HESITANT_AWARE / FLAGGED_HUMAN across 9 Indian languages
- **Hesitation response** — bot replies with targeted address, transport offer, or safety reassurance
- **Decline taxonomy** — TRANSPORT / TIMING / HEALTH / AWARENESS / OTHER feeds admin insights
- **Human escalation** — abuse, distress, or ambiguous replies flagged for coordinator review

## Tech Stack
- **AWS Lambda** — MatchingLambda, OutreachLambda, BotLambda, EscalationLambda, AdminLambda
- **Amazon Bedrock** — Claude 3 Haiku for outreach and intent classification
- **Amazon DynamoDB** — Donors, Patients, MatchRequests, BotSessions
- **Amazon SNS + EventBridge** — event bus and 30-min escalation trigger
- **Twilio WhatsApp** — donor outreach channel
- **AWS Amplify** — React + Vite + Tailwind frontend, auto-deploy from GitHub

## Matching Algorithm
5-factor weighted scoring (100 pts total):
- Distance via Haversine — 30 pts
- Reliability (calls-to-donations ratio) — 25 pts  
- Loyalty (lifetime donations) — 20 pts
- Donor type (Regular/Emergency/Bridge) — 15 pts
- Recency (last contacted date) — 10 pts

Hard eligibility gates applied before scoring: blood compatibility, active status, next eligible date.

## Hackathon
AI For Good 2.0 — Blood Warriors Foundation problem statement
