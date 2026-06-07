import json
import boto3
from collections import Counter
from decimal import Decimal

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
match_requests_table = dynamodb.Table('MatchRequests')
donors_table = dynamodb.Table('Donors')

CORS_HEADERS = {
    'Content-Type':                'application/json',
    'Access-Control-Allow-Origin': '*',
}


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def reliability_pct(ratio):
    try:
        r = min(float(ratio), 5.0)
    except (TypeError, ValueError):
        return 50
    return round((1 - r / 5.0) * 100)


def loyalty_tier(donations):
    try:
        d = float(donations)
    except (TypeError, ValueError):
        d = 0
    if d > 8:
        return 'Gold'
    if d >= 4:
        return 'Silver'
    return 'Bronze'


def lookup_donor_by_phone(phone):
    scan_kwargs = {
        'FilterExpression': '#p = :phone',
        'ExpressionAttributeNames': {'#p': 'phone'},
        'ExpressionAttributeValues': {':phone': phone},
    }
    donor = None
    while True:
        resp = donors_table.scan(**scan_kwargs)
        items = resp.get('Items', [])
        if items:
            donor = items[0]
            break
        if 'LastEvaluatedKey' not in resp:
            break
        scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']

    if not donor:
        return {
            'statusCode': 404,
            'headers': CORS_HEADERS,
            'body': json.dumps({'error': 'No donor found with this phone number'}),
        }

    donations = donor.get('donations_till_date', 0)
    profile = {
        'donor_id':            str(donor.get('user_id', '')),
        'name':                str(donor.get('name', '')),
        'blood_group':         str(donor.get('blood_group', '')),
        'city':                str(donor.get('city', '')),
        'donations_till_date': donations,
        'last_donated_date':   str(donor.get('last_donation_date', '')),
        'next_eligible_date':  str(donor.get('next_eligible_date', '')),
        'eligibility_status':  str(donor.get('eligibility_status', '')),
        'donor_type':          str(donor.get('donor_type', '')),
        'reliability_score':   reliability_pct(donor.get('calls_to_donations_ratio', 2.5)),
        'loyalty_tier':        loyalty_tier(donations),
    }

    return {
        'statusCode': 200,
        'headers': CORS_HEADERS,
        'body': json.dumps(profile, default=decimal_default),
    }


def lambda_handler(event, context):
    # Donor self-service lookup: GET /admin?phone=<number>
    query_params = event.get('queryStringParameters') or {}
    if query_params.get('phone'):
        return lookup_donor_by_phone(str(query_params['phone']).strip())

    # Scan all MatchRequests (paginated)
    resp  = match_requests_table.scan()
    items = list(resp.get('Items', []))
    while 'LastEvaluatedKey' in resp:
        resp  = match_requests_table.scan(ExclusiveStartKey=resp['LastEvaluatedKey'])
        items.extend(resp.get('Items', []))

    items.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    status_counts      = Counter(i.get('status', 'unknown') for i in items)
    blood_group_counts = Counter(i.get('patient_blood_group', 'Unknown') for i in items)

    intent_counts  = Counter()
    decline_counts = Counter()

    human_escalation_count = 0
    human_escalations      = []

    for item in items:
        dr = item.get('donor_response')
        if dr and isinstance(dr, dict):
            intent_counts[dr.get('intent', 'UNKNOWN')] += 1

        # decline_reason is written at the top-level of the MatchRequest item
        # (set when intent=NO and a reason was detected)
        reason = item.get('decline_reason')
        if reason:
            decline_counts[reason] += 1

        if item.get('human_escalation_flag') is True:
            human_escalation_count += 1
            human_escalations.append({
                'request_id': str(item.get('request_id', '')),
                'message':    str(item.get('human_escalation_reason', '')),
                'created_at': str(item.get('created_at', '')),
            })

    total        = len(items)
    confirmed    = status_counts.get('confirmed', 0)
    success_rate = round(confirmed / total * 100, 1) if total > 0 else 0

    total_escalations = sum(int(i.get('escalation_count', 0)) for i in items)
    avg_escalations   = round(total_escalations / total, 2) if total > 0 else 0

    # Hesitation breakdown: count HESITANT_LOGISTICS and HESITANT_AWARE intents
    hesitation_logistics = intent_counts.get('HESITANT_LOGISTICS', 0)
    hesitation_aware     = intent_counts.get('HESITANT_AWARE', 0)

    # Donation follow-up outcomes: did confirmed donors actually donate?
    donation_confirmed_count = sum(1 for i in items if i.get('donation_confirmed') is True)
    donation_pending_count   = sum(1 for i in items if i.get('status') == 'confirmed' and not i.get('donation_confirmed'))

    requests = []
    for item in items:
        requests.append({
            'request_id':          str(item.get('request_id', '')),
            'patient_blood_group': str(item.get('patient_blood_group', '')),
            'status':              str(item.get('status', '')),
            'current_donor_rank':  int(item.get('current_donor_rank', 0)),
            'escalation_count':    int(item.get('escalation_count', 0)),
            'created_at':          str(item.get('created_at', '')),
            'last_outreach_at':    str(item.get('last_outreach_at', '')),
            'responded_at':        str(item.get('responded_at', '')),
            'donor_response':      item.get('donor_response'),
            'decline_reason':      item.get('decline_reason'),
        })

    result = {
        'total':               total,
        'success_rate':        success_rate,
        'avg_escalations':     avg_escalations,
        'status_counts':       dict(status_counts),
        'intent_counts':       dict(intent_counts),
        'blood_group_demand':  dict(blood_group_counts),
        # --- new fields ---
        'decline_reasons':     dict(decline_counts),
        'hesitation_breakdown': {
            'logistics': hesitation_logistics,
            'awareness': hesitation_aware,
        },
        'human_escalation_count': human_escalation_count,
        'human_escalations':      human_escalations,
        'donation_outcomes': {
            'confirmed': donation_confirmed_count,
            'pending':   donation_pending_count,
        },
        'requests':            requests,
    }

    return {
        'statusCode': 200,
        'headers': CORS_HEADERS,
        'body': json.dumps(result, default=decimal_default),
    }