import boto3
import json

def lambda_handler(event, context):
    
    print(str(event))
    inputParam = json.loads(event['body'])
    s3_bucket_name = inputParam['s3_bucket_name']
    customer_master_key = inputParam['customer_master_key']
    region = inputParam['region']
    status_code = 201
    status_message = ""
    
    print("s3_bucket_name="+s3_bucket_name)
    print("customer_master_key="+customer_master_key)
    print("region="+region)
    
    client = boto3.client('s3', region_name=region)

    try:
        client.head_bucket(Bucket=s3_bucket_name)
        print("bucket does exist!")
        s3_response = client.put_bucket_encryption(
            Bucket=s3_bucket_name,
            ServerSideEncryptionConfiguration={
                'Rules': [
                    {
                        'ApplyServerSideEncryptionByDefault': {
                        'SSEAlgorithm': 'aws:kms',
                        'KMSMasterKeyID': customer_master_key
                        }
                    },
                ]
            }
        )
        status_code = 200
        status_message = "KMS encryption applied successfully"

    except:
        status_code = 201
        status_message = "Error while processing your request. Please check \
                                if {0} bucket and {1} KMS key exist".\
                                format(s3_bucket_name, customer_master_key)
    print(str(status_message))
    return {
        'statusCode': status_code,
        'isBase64Encoded': False,
        'headers': {"Content-Type":"application/json"},
        'body': json.dumps({'message': status_message})
    }
