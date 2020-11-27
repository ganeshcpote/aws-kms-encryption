import json
import boto3, os
import requests
from requests_aws4auth import AWS4Auth
from datetime import datetime
import time

target_endpoint=""
source_endpoint=""

def lambda_handler(event, context):
    
    inputParam = json.loads(event['body'])
    es_domain_name = inputParam['es_domain_name']
    customer_master_key = inputParam['customer_master_key']
    region = inputParam['region']
    
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, 'es', session_token=credentials.token)
    
    client = boto3.client('es')
    response = client.describe_elasticsearch_domain(DomainName=es_domain_name)
    print(str(response))
    
    #check_status = client.describe_elasticsearch_domain(DomainName='zurich-iverify-pro-ganesh')
    #print(str(check_status))
    #return "exit now"
    
    source_domain = response['DomainStatus']
    new_domain_name="{0}-gp0605".format(str(source_domain['DomainName'])[0:18])
    print("new domain name = "+ str(new_domain_name))
    
    access_policy = {
               "Version": "2012-10-17",
               "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                    "AWS": "*"
                  },
                  "Action": "es:*",
                  "Resource": "arn:aws:es:us-east-1:xxxx:domain/"+new_domain_name+"/*"
               }
            ]
       }
    
    new_response = client.create_elasticsearch_domain(
        DomainName= new_domain_name,
        ElasticsearchVersion=source_domain['ElasticsearchVersion'],
        ElasticsearchClusterConfig={
            'InstanceType': source_domain['ElasticsearchClusterConfig']['InstanceType'],
            'InstanceCount': source_domain['ElasticsearchClusterConfig']['InstanceCount'],
            'DedicatedMasterEnabled': source_domain['ElasticsearchClusterConfig']['DedicatedMasterEnabled'],
            'ZoneAwarenessEnabled': source_domain['ElasticsearchClusterConfig']['ZoneAwarenessEnabled'],
            #'ZoneAwarenessConfig': {
            #    'AvailabilityZoneCount': source_domain['ElasticsearchClusterConfig']['ZoneAwarenessConfig']['AvailabilityZoneCount']
            #}
        },
        EBSOptions={
            'EBSEnabled': source_domain['EBSOptions']['EBSEnabled'],
            'VolumeType': source_domain['EBSOptions']['VolumeType'],
            'VolumeSize': source_domain['EBSOptions']['VolumeSize']
        },
        #SnapshotOptions={
        #    'AutomatedSnapshotStartHour': source_domain['SnapshotOptions']['AutomatedSnapshotStartHour']
        #},
        VPCOptions={
            'SubnetIds': source_domain['VPCOptions']['SubnetIds'],
            'SecurityGroupIds': source_domain['VPCOptions']['SecurityGroupIds']
        },    
        EncryptionAtRestOptions={
            'Enabled': True,
            'KmsKeyId': customer_master_key
        },
        AdvancedOptions=source_domain['AdvancedOptions'],
        #LogPublishingOptions=source_domain['LogPublishingOptions'],
        DomainEndpointOptions=source_domain['DomainEndpointOptions'],
        NodeToNodeEncryptionOptions=source_domain['NodeToNodeEncryptionOptions'],
        CognitoOptions=source_domain['CognitoOptions'],
        AccessPolicies=json.dumps(access_policy)
    )
    
    print(str(new_response))
    
    count=0;
    while True:
        check_status = client.describe_elasticsearch_domain(DomainName=new_domain_name)
        processing_status=check_status['DomainStatus']['Processing']
        print("Processing status for new ES domain for use : IsProcessing={0}".format(processing_status))
        if not processing_status:
            break
        
        if count == 10:
            print("Waiting for ES cluster to be up and running till 10 minutes")
            print("Next wait operation will be perform on elasticsearch_encryption lambda function")
            break
        time.sleep(60) # Delay for 1 minute (60 seconds).
        count=count+1
    
    #time.sleep(60)
    #check_status = client.describe_elasticsearch_domain(DomainName=new_domain_name)
    #print(str(check_status))
    #target_endpoint = check_status['DomainStatus']['Endpoints']['vpc']
    #print(str("Target ES domain endpoint is " + target_endpoint))
    
    #if target_endpoint == "":
    #    return "Target endpoint is missing..."
    
    source_endpoint=response['DomainStatus']['Endpoints']['vpc']
    
    if source_endpoint == "":
        return "Source endpoint is missing..."
    
    print(str("Source ES domain endpoint is " + target_endpoint))
    
    json_body = {
                   "source_endpoint":source_endpoint,
                   "target_endpoint":new_domain_name,
                   "customer_master_key":customer_master_key,
                   "region":region,
                   "s3_bucket":es_domain_name
                }
    
    print("Calling elasticsearch_encryption to take and restore snapshot to newly created EC cluster")
    client = boto3.client("lambda")
    response=client.invoke(FunctionName='arn:aws:lambda:us-east-1:xxx:function:elasticsearch_encryption',\
                                InvocationType='Event', Payload=json.dumps(json_body))
        
    # TODO implement
    return {
        'statusCode': 200,
        'body': json.dumps('Success!')
    }
