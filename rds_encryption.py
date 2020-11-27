import json
import boto3
import botocore
import datetime
import time

def lambda_handler(event, context):
    
    print(str(event))
    inputParam = json.loads(event['body'])
    db_instance_identifier = inputParam['db_instance_identifier']
    customer_master_key = inputParam['customer_master_key']
    region = inputParam['region']
    securitygroup = inputParam['securitygroup']
    status_code = 200
    status_message = "RDS encryption completed successfully"
    
    print("db_instance_identifier="+db_instance_identifier)
    print("customer_master_key="+customer_master_key)
    print("region="+region)
    
    client = boto3.client('rds', region_name=region)
    waiter_snapshot_exists = client.get_waiter('db_cluster_snapshot_available')
    
    today = datetime.date.today()
    print('Check if {} rds instance is exist...'.format(db_instance_identifier))

    response = client.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)
    print(str(response))
    if('errorMessage' in response):
        print(str(response['errorMessage']))
    else:
        print("{} rds instance found...".format(db_instance_identifier))
        print("{}-{:%Y-%m-%d} snapshot creation started...".format(db_instance_identifier, today))
        snapshot = client.create_db_snapshot(
                DBInstanceIdentifier=db_instance_identifier,
                DBSnapshotIdentifier="{}-{:%Y-%m-%d}".format(db_instance_identifier, today),
            )
        
        print("{} snapshot started creating".format(snapshot['DBSnapshot']['DBSnapshotIdentifier']))
        wait_for_snapshot_to_be_ready(client, snapshot['DBSnapshot'])
        print("{}-{:%Y-%m-%d} Snapshot created.".format(snapshot['DBSnapshot']['DBSnapshotIdentifier'], today))
        
        if ':' in snapshot['DBSnapshot']['DBSnapshotIdentifier']:
            target_db_snapshot_id = "{}-recrypted".format(snapshot['DBSnapshot']['DBSnapshotIdentifier'].split(':')[1])
        else:
            target_db_snapshot_id = "{}-recrypted".format(snapshot['DBSnapshot']['DBSnapshotIdentifier'])

        print("{} ecrypted snapshot copy creation started...".format(target_db_snapshot_id))
        recrypted_copy = client.copy_db_snapshot(
                SourceDBSnapshotIdentifier=snapshot['DBSnapshot']['DBSnapshotIdentifier'],
                TargetDBSnapshotIdentifier=target_db_snapshot_id,
                KmsKeyId=customer_master_key
            )
        wait_for_snapshot_to_be_ready(client, recrypted_copy['DBSnapshot'])
        print("{} ecrypted snapshot copy created successfully...".format(target_db_snapshot_id))
        
        print("Restoring RDS instance {} from snapshot {}".format(db_instance_identifier, recrypted_copy['DBSnapshot']['DBSnapshotIdentifier']))
        source_instance=response['DBInstances'][0]
        instance = client.restore_db_instance_from_db_snapshot(
                DBInstanceIdentifier="{}-encrypted".format(db_instance_identifier),
                DBSnapshotIdentifier=recrypted_copy['DBSnapshot']['DBSnapshotArn'],
                DBInstanceClass=source_instance['DBInstanceClass'],
                AvailabilityZone=source_instance['AvailabilityZone'],
                DBSubnetGroupName=source_instance['DBSubnetGroup']['DBSubnetGroupName'],
                MultiAZ=source_instance['MultiAZ'],
                PubliclyAccessible=source_instance['PubliclyAccessible'],
                AutoMinorVersionUpgrade=source_instance['AutoMinorVersionUpgrade'],
                LicenseModel=source_instance['LicenseModel'],
                Engine=source_instance['Engine'],
                StorageType=source_instance['StorageType'],
                CopyTagsToSnapshot=True,
                DBParameterGroupName=source_instance['DBParameterGroups'][0]['DBParameterGroupName'],
                DeletionProtection=source_instance['DeletionProtection']
            )
        wait_for_instance_to_be_ready(client, instance)
        print("  RDS instance restored.")
        print("  Applying security groups - started")
        modify_rds_instance_security_groups(client, instance['DBInstance']['DBInstanceIdentifier'], securitygroup)
        print("  Applying security groups - completed")
        print("  RDS encryption process completed...")

    return {
        'statusCode': status_code,
        'isBase64Encoded': False,
        'headers': {"Content-Type":"application/json"},
        'body': json.dumps({'message': status_message})
    }


def wait_for_instance_to_be_ready(rds_client, instance):
	# simply check if the specified instance is healthy every 5 seconds until it
	# is
	while True:
		instancecheck = rds_client.describe_db_instances(DBInstanceIdentifier=instance['DBInstance']['DBInstanceIdentifier'])['DBInstances'][0]
		if instancecheck['DBInstanceStatus'] == 'available':
			print("  Instance {} ready and available!".format(instance['DBInstance']['DBInstanceIdentifier']))
			break
		else:
			print("Instance creation in progress, sleeping 10 seconds...")
			time.sleep(10)

def modify_rds_instance_security_groups(rds_client, instancename, securitygroup):

    print("Modifying RDS instance to attach correct securitygroup")
    try:
        rds_client.modify_db_instance(
            DBInstanceIdentifier=instancename,
            VpcSecurityGroupIds=[
                securitygroup
            ],
            ApplyImmediately=True
        )
        print("  RDS Instance {} modified".format(instancename))
    except Exception as e:
        raise

def wait_for_snapshot_to_be_ready(rds_client, snapshot):

    # simply check if the specified snapshot is healthy every 5 seconds until it
    # is
    while True:
        snapshotcheck = rds_client.describe_db_snapshots(DBSnapshotIdentifier=snapshot['DBSnapshotIdentifier'])['DBSnapshots'][0]
        if snapshotcheck['Status'] == 'available':
            print("  Snapshot {} complete and available!".format(snapshot['DBSnapshotIdentifier']))
            break
        else:
            print("Snapshot {} in progress, {}% complete".format(snapshot['DBSnapshotIdentifier'], snapshotcheck['PercentProgress']))
            time.sleep(10)