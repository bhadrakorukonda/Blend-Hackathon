import boto3
from decimal import Decimal
from datetime import datetime, date
import math

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
donors_table = dynamodb.Table('Donors')
patients_table = dynamodb.Table('Patients')

# --- Blood compatibility map ---
# Key = donor blood group, Value = list of recipient blood groups they can donate to
BLOOD_COMPAT = {
    "O Negative":  ["O Negative","O Positive","A Negative","A Positive","B Negative","B Positive","AB Negative","AB Positive"],
    "O Positive":  ["O Positive","A Positive","B Positive","AB Positive"],
    "A Negative":  ["A Negative","A Positive","AB Negative","AB Positive"],
    "A Positive":  ["A Positive","AB Positive"],
    "B Negative":  ["B Negative","B Positive","AB Negative","AB Positive"],
    "B Positive":  ["B Positive","AB Positive"],
    "AB Negative": ["AB Negative","AB Positive"],
    "AB Positive": ["AB Positive"],
}

def sanitize(obj):
    """Recursively convert Decimals to float/int for JSON safety."""
    if isinstance(obj, list):
        return [sanitize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate straight-line distance between two GPS coordinates in km."""
    R = 6371
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlam = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def distance_score(km):
    """30 points max. Full points under 50km, zero at 500km, linear in between."""
    if km <= 50:
        return 30.0
    if km >= 500:
        return 0.0
    return 30.0 * (1 - (km - 50) / 450)

def reliability_score(ratio):
    """25 points max. Lower calls_to_donations_ratio = more reliable donor."""
    try:
        r = float(ratio)
    except:
        return 12.5  # default to midpoint if missing
    r = min(r, 5.0)  # clamp at 5
    return 25.0 * (1 - r / 5.0)

def loyalty_score(donations):
    """20 points max. Based on total donations, max in dataset is 12."""
    try:
        d = float(donations)
    except:
        return 0.0
    return 20.0 * min(d / 12.0, 1.0)

def donor_type_score(donor_type):
    """15 points max."""
    if str(donor_type).strip() == 'Regular Donor':
        return 15.0
    if str(donor_type).strip() == 'One-Time Donor':
        return 5.0
    return 8.0  # Other/unknown

def recency_score(last_contacted_date):
    """10 points max. Penalise if contacted within last 7 days."""
    if not last_contacted_date or str(last_contacted_date).strip() in ('', 'None', 'nan'):
        return 10.0  # never contacted = full points
    try:
        last = datetime.strptime(str(last_contacted_date).strip(), '%Y-%m-%d').date()
        days_ago = (date.today() - last).days
        if days_ago < 7:
            return 0.0  # contacted too recently
        return 10.0
    except:
        return 10.0

def passes_hard_gates(donor, patient_blood_group):
    """Returns True only if donor clears all hard filters."""
    # Gate 1 — must be eligible
    if str(donor.get('eligibility_status', '')).strip().lower() != 'eligible':
        return False
    # Gate 2 — must be active
    if str(donor.get('user_donation_active_status', '')).strip().lower() != 'active':
        return False
    # Gate 3 — cooldown check
    ned = str(donor.get('next_eligible_date', '')).strip()
    if ned and ned not in ('', 'None', 'nan'):
        try:
            next_date = datetime.strptime(ned, '%Y-%m-%d').date()
            if next_date > date.today():
                return False  # still in cooldown
        except:
            pass
    # Gate 4 — blood compatibility
    donor_bg = str(donor.get('blood_group', '')).strip()
    compatible_recipients = BLOOD_COMPAT.get(donor_bg, [])
    if patient_blood_group not in compatible_recipients:
        return False
    return True

def score_donor(donor, patient):
    """Score a single donor against a patient. Returns float 0-100."""
    km = haversine_km(
        donor.get('latitude', 0), donor.get('longitude', 0),
        patient.get('latitude', 0), patient.get('longitude', 0)
    )
    score = (
        distance_score(km) +
        reliability_score(donor.get('calls_to_donations_ratio', 2.5)) +
        loyalty_score(donor.get('donations_till_date', 0)) +
        donor_type_score(donor.get('donor_type', '')) +
        recency_score(donor.get('last_contacted_date', ''))
    )
    return round(score, 2), round(km, 1)

def find_top_donors(patient_id, top_n=5):
    """Main function — fetch patient, scan donors, apply gates, score, return top N."""
    # Fetch patient
    resp = patients_table.get_item(Key={'user_id': patient_id})
    patient = resp.get('Item')
    if not patient:
        return {'error': f'Patient {patient_id} not found'}

    patient_blood_group = str(patient.get('bridge_blood_group') or patient.get('blood_group', '')).strip()
    print(f"\nPatient: {patient_id} | Needs: {patient_blood_group}")

    # Scan all donors (for hackathon scale this is fine)
    all_donors = []
    scan_kwargs = {}
    while True:
        response = donors_table.scan(**scan_kwargs)
        all_donors.extend(response['Items'])
        if 'LastEvaluatedKey' not in response:
            break
        scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

    print(f"Total donors in DB: {len(all_donors)}")

    # Apply hard gates + score
    results = []
    passed_gates = 0
    for donor in all_donors:
        if not passes_hard_gates(donor, patient_blood_group):
            continue
        passed_gates += 1
        score, km = score_donor(donor, patient)
        results.append(sanitize({
            'user_id': donor.get('user_id'),
            'name': donor.get('name', 'Unknown'),
            'blood_group': donor.get('blood_group'),
            'score': score,
            'distance_km': km,
            'calls_to_donations_ratio': donor.get('calls_to_donations_ratio', 'N/A'),
            'donations_till_date': donor.get('donations_till_date', '0'),
            'donor_type': donor.get('donor_type', ''),
            'phone': donor.get('phone', donor.get('mobile', '')),
        }))

    print(f"Passed hard gates: {passed_gates}")

    # Sort by score descending, take top N
    results.sort(key=lambda x: x['score'], reverse=True)
    top = results[:top_n]

    print(f"\nTop {top_n} donors:")
    for i, d in enumerate(top, 1):
        print(f"  {i}. {d['user_id']} | Score: {d['score']} | "
              f"Distance: {d['distance_km']}km | "
              f"Ratio: {d['calls_to_donations_ratio']} | "
              f"Blood: {d['blood_group']}")

    return {
        'patient_id': patient_id,
        'patient_blood_group': patient_blood_group,
        'top_donors': top
    }

if __name__ == '__main__':
    print("Fetching a sample patient to test with...")
    resp = patients_table.scan(Limit=1)
    if resp['Items']:
        sample_patient = resp['Items'][0]
        pid = sample_patient['user_id']
        print(f"Using patient: {pid} | Blood group: {sample_patient.get('bridge_blood_group') or sample_patient.get('blood_group')}")
        find_top_donors(pid)
    else:
        print("No patients found in DB!")