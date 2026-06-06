import boto3
import pandas as pd
from decimal import Decimal
import json
import math

# Connect to DynamoDB in Mumbai region
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')

donors_table = dynamodb.Table('Donors')
patients_table = dynamodb.Table('Patients')

def clean_value(val):
    """Convert value to DynamoDB-safe type. DynamoDB doesn't accept NaN or float('nan')."""
    if val is None:
        return None
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return Decimal(str(round(val, 6)))
    return val

def load_csv(filepath):
    df = pd.read_csv(filepath, dtype=str)  # read everything as string first
    df = df.where(pd.notnull(df), None)    # replace NaN with None

    donor_count = 0
    patient_count = 0
    error_count = 0

    # Use batch_writer for speed — sends 25 records at a time
    with donors_table.batch_writer() as donor_batch, \
         patients_table.batch_writer() as patient_batch:

        for idx, row in df.iterrows():
            try:
                # Build a clean item dict, skipping empty values
                item = {}
                for col in df.columns:
                    val = row[col]
                    if val is None or val == '' or val == 'nan':
                        continue
                    # Try to convert numeric strings to Decimal for DynamoDB
                    try:
                        if '.' in str(val):
                            item[col] = Decimal(str(float(val)))
                        else:
                            item[col] = str(val)
                    except:
                        item[col] = str(val)

                role = str(row.get('role', '')).strip()
                user_id = str(row.get('user_id', '')).strip()

                if not user_id or user_id == 'None':
                    continue

                # Route to correct table based on role
                if role == 'Patient':
                    patient_batch.put_item(Item=item)
                    patient_count += 1
                else:
                    # Emergency Donor, Bridge Donor, Volunteer, Guest all go to Donors
                    donor_batch.put_item(Item=item)
                    donor_count += 1

                if (idx + 1) % 500 == 0:
                    print(f"  Processed {idx + 1} rows...")

            except Exception as e:
                error_count += 1
                if error_count <= 5:  # only print first 5 errors
                    print(f"  Error on row {idx}: {e}")

    print(f"\n✅ Done!")
    print(f"   Donors loaded:   {donor_count}")
    print(f"   Patients loaded: {patient_count}")
    print(f"   Errors skipped:  {error_count}")

if __name__ == '__main__':
    load_csv('H:\Random projects\Blend Hackathon\Dataset.csv')