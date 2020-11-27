import json
import boto3, os
import requests
from requests_aws4auth import AWS4Auth
from datetime import datetime
import time

target_endpoint=""

def lambda_handler(event, context):
    
    print(str(event))
    source_endpoint = 'https://'+ event['source_endpoint']
    
    target_domain_name=event['target_endpoint']
    #target_endpoint = 'https://'+ event['target_endpoint']
    customer_master_key = event['customer_master_key']
    
    es_domain_name = event['s3_bucket']
    region = event['region']
    
    print (" Source EC Domain : " + source_endpoint)
    print (" Target EC Domain : " + target_domain_name)
    print (" KMS Key : " + customer_master_key)
    print (" Region : " + region)
    
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, 'es', session_token=credentials.token)
    client = boto3.client('es')
    
    while True:
        check_status = client.describe_elasticsearch_domain(DomainName=target_domain_name)
        processing_status=check_status['DomainStatus']['Processing']
        print("Processing status for new ES domain for use : IsProcessing={0}".format(processing_status))
        if not processing_status:
            break
        time.sleep(60) # Delay for 1 minute (60 seconds).
		
    time.sleep(60)
    check_status = client.describe_elasticsearch_domain(DomainName=target_domain_name)
    print(str(check_status))
    target_endpoint = "https://" + check_status['DomainStatus']['Endpoints']['vpc']
    print(str("Target ES domain endpoint is " + target_endpoint))
    
    if target_endpoint == "":
    	return "Target endpoint is missing..."

    print("Repository registration process started...")
    host= source_endpoint
    region=str(os.getenv('region',region))
    s3Bucket='es-encryption-prod-us'
    s3RepoName=es_domain_name+'-snapshot-repo'
    roleArn=str(os.getenv('roleArn','arn:aws:iam::xxx:role/es-encryption-prod-us'))
    
    datestamp = datetime.now().strftime('%Y-%m-%dt%H:%M:%S')
    
    # Register repository
    # the Elasticsearch API endpoint
    path = '/_snapshot/'+s3RepoName
    url = host + path

    payload = {
    "type": "s3",
    "settings": {
        "bucket": s3Bucket,
        "base_path": es_domain_name,
        "endpoint": "s3.amazonaws.com",
        "role_arn": roleArn
        }
    }

    headers = {"Content-Type": "application/json"}
    
    print("{0} API will be called to register the source snapshot".format(url))
    r = requests.put(url, auth=awsauth, json=payload, headers=headers)
    print(r.status_code)
    print(r.text)
    print("Repository registration process Completed...")
    
    print("Snapshot creation process started...")

    # Take snapshot - Even though this looks similar to above, but this code is required to take snapshot.
    path = '/_snapshot/'+s3RepoName+'/snapshot-'+datestamp
    url = host + path
    
    print("{0} API will be called to take the source snapshot".format(url))
    r = requests.put(url, auth=awsauth)
    print(r.text)
    print(r.status_code)
    print("'{0}' host snapshot creation started using '{1}' repo on '{2}' S3 bucket".format(host,s3RepoName,s3Bucket))
    
    while True:
        path='/_snapshot/'+ s3RepoName +'/snapshot-'+datestamp
        url = host + path
        r = requests.get(url, auth=awsauth)
        snapshots=json.loads(r.text)
        print(r.text)
        print(r.status_code)
        if str(snapshots['snapshots'][0]['state'])=='SUCCESS':
            print("'{0}' host snapshot created successfully using '{1}' repo on '{2}' S3 bucket".format(host,s3RepoName,s3Bucket))
            break
    print("Snapshot creation process Completed...")
    
    
    print("New ES domain repository registration process started...")
    
    # Register existing repository to new Elasticsearch cluster
    # the Elasticsearch API endpoint
    s3RepoName= es_domain_name + '-restore-repo'
    
    path = '/_snapshot/'+s3RepoName
    url = target_endpoint + path
    payload = {
    "type": "s3",
    "settings": {
        "bucket": s3Bucket,
        "base_path": es_domain_name,
        "endpoint": "s3.amazonaws.com",
        "role_arn": roleArn
        }
    }
    headers = {"Content-Type": "application/json"}
    
    print("{0} API will be called to take the destination snapshot repo".format(url))
    r = requests.put(url, auth=awsauth, json=payload, headers=headers)
    print(r.status_code)
    print(r.text)
    
    print("New ES domain repository registration process completed...")
    
    print("Deleting .kibana index from new ES domain to avoid duplicity...")
    
    # delete the existing .kibana_1 index before restoring snapshot
    path = '/.kibana_1'
    url = target_endpoint + path
    
    print("{0} API will be called to delete the default index".format(url))
    r = requests.delete(url, auth=awsauth)

    print("Snapshot restore process started...")

    # restore the existing snapshot to new Elasticsearch cluster by renaming existing index to new one
    payload = {
      "indices": "*",
      "ignore_unavailable": "true",
      "include_global_state": "true",
      "rename_pattern": ".kibana",
      "rename_replacement": "restored_.kibana"
    }
    headers = {"Content-Type": "application/json"}
    path = '/_snapshot/'+s3RepoName+'/snapshot-'+datestamp+'/_restore'
    url = target_endpoint + path
    #r = requests.post(url, auth=awsauth, json=payload, headers=headers)
    
    print("{0} API will be called to restore the snapshot to destination ES domain".format(url))
    r = requests.post(url, auth=awsauth)
    print(r.text)
    print(r.status_code)
    print("Snapshot restore process completed...")
    
    
    # rename the restored index to .kibana in new Elasticsearch cluster
    payload = {
      "source": {
        "index": "restored_.kibana"
      },
      "dest": {
        "index": ".kibana"
      }
    }
    
    # TODO implement
    return {
        'statusCode': 200,
        'body': json.dumps('Success!')
    }
