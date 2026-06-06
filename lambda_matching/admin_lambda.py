import json
import boto3
from collections import Counter
from decimal import Decimal

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
match_requests_table = dynamodb.Table('MatchRequests')


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def lambda_handler(event, context):
    # Scan all MatchRequests (paginated)
    resp  = match_requests_table.scan()
    items = list(resp.get('Items', []))
    while 'LastEvaluatedKey' in resp:
        resp  = match_requests_table.scan(ExclusiveStartKey=resp['LastEvaluatedKey'])
        items.extend(resp.get('Items', []))

    items.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    status_counts     = Counter(i.get('status', 'unknown') for i in items)
    blood_group_counts = Counter(i.get('patient_blood_group', 'Unknown') for i in items)

    intent_counts = Counter()
    for item in items:
        dr = item.get('donor_response')
        if dr and isinstance(dr, dict):
            intent_counts[dr.get('intent', 'UNKNOWN')] += 1

    total        = len(items)
    confirmed    = status_counts.get('confirmed', 0)
    success_rate = round(confirmed / total * 100, 1) if total > 0 else 0

    total_escalations = sum(int(i.get('escalation_count', 0)) for i in items)
    avg_escalations   = round(total_escalations / total, 2) if total > 0 else 0

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
        })

    result = {
        'total':              total,
        'success_rate':       success_rate,
        'avg_escalations':    avg_escalations,
        'status_counts':      dict(status_counts),
        'intent_counts':      dict(intent_counts),
        'blood_group_demand': dict(blood_group_counts),
        'requests':           requests,
    }

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type':                'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps(result, default=decimal_default),
    }
