import json
import boto3
import botocore
import datetime
import time

def lambda_handler(event, context):
    
    print(str(event))
    inputParam = json.loads(event['body'])
    db_cluster_name = inputParam['db_cluster_name']
    customer_master_key = inputParam['customer_master_key']
    region = inputParam['region']
    status_code = 200
    status_message = "RDS encryption completed successfully"
    
    print("db_cluster_name="+db_cluster_name)
    print("customer_master_key="+customer_master_key)
    print("region="+region)
    
    client = boto3.client('rds', region_name=region)
    waiter_snapshot_exists = client.get_waiter('db_cluster_snapshot_available')
    
    today = datetime.date.today()
    print('Check if {} rds instance is exist...'.format(db_cluster_name))
    
    response = client.describe_db_clusters(DBClusterIdentifier=db_cluster_name)
    print(str(response))
    if('errorMessage' in response):
        print(str(response['errorMessage']))
    else:
        print("db cluster present")
        print("{} rds cluster found...".format(db_cluster_name))
        print("{}-{:%Y-%m-%d} snapshot creation started...".format(db_cluster_name, today))
        snapshot = client.create_db_cluster_snapshot(
                DBClusterIdentifier=db_cluster_name,
                DBClusterSnapshotIdentifier="{}-{:%Y-%m-%d}".format(db_cluster_name, today),
            )
        print("{} snapshot started creating".format(snapshot['DBClusterSnapshot']['DBClusterSnapshotIdentifier']))
        wait_for_snapshot_to_be_ready(client, snapshot['DBClusterSnapshot'])
        print("{}-{:%Y-%m-%d} Snapshot created.".format(snapshot['DBClusterSnapshot']['DBClusterSnapshotIdentifier'], today))
        
        instance = client.restore_db_cluster_from_snapshot(DBClusterIdentifier="{}-encrypted".format(snapshot['DBClusterSnapshot']['DBClusterIdentifier']),
                                                        SnapshotIdentifier=snapshot['DBClusterSnapshot']['DBClusterSnapshotIdentifier'],
                                                        Engine=response['DBClusters'][0]['Engine'],
                                                        EngineVersion=response['DBClusters'][0]['EngineVersion'],
                                                        DBSubnetGroupName=response['DBClusters'][0]['DBSubnetGroup'],
                                                        KmsKeyId=customer_master_key,
                                                        EngineMode=response['DBClusters'][0]['EngineMode'],
                                                        AvailabilityZones=response['DBClusters'][0]['AvailabilityZones'],
                                                        DatabaseName=response['DBClusters'][0]['DatabaseName'],
                                                        DBClusterParameterGroupName=response['DBClusters'][0]['DBClusterParameterGroup'],
                                                        DeletionProtection=response['DBClusters'][0]['DeletionProtection'],
                                                        VpcSecurityGroupIds=[response['DBClusters'][0]['VpcSecurityGroups'][0]['VpcSecurityGroupId']],
                                                        CopyTagsToSnapshot=True)
        print("instance = " + str(instance))
        wait_for_instance_to_be_ready(client, instance)
        print("  RDS cluster instance restored.")
        
        db_cluster_members=response['DBClusters'][0]['DBClusterMembers']
        for member in db_cluster_members:
            #if member['IsClusterWriter']==True:
            #    print("Writer Node")
            writer_node = client.describe_db_instances(DBInstanceIdentifier=member['DBInstanceIdentifier'])
            print("  Adding writer instances to RDS cluster")
            source_instance=writer_node['DBInstances'][0]
            instance_response= client.create_db_instance( DBClusterIdentifier = instance['DBCluster']['DBClusterIdentifier'],
                                                  DBInstanceIdentifier = "{}-encrypted".format(source_instance['DBInstanceIdentifier']),
                                                  Engine=source_instance['Engine'],
                                                  CopyTagsToSnapshot=True,
                                                  DBInstanceClass=source_instance['DBInstanceClass'],
                                                  AvailabilityZone=source_instance['AvailabilityZone'],
                                                  DBSubnetGroupName=source_instance['DBSubnetGroup']['DBSubnetGroupName'],
                                                  MultiAZ=instance['DBCluster']['MultiAZ'],
                                                  PubliclyAccessible=source_instance['PubliclyAccessible'],
                                                  AutoMinorVersionUpgrade=source_instance['AutoMinorVersionUpgrade'],
                                                  LicenseModel=source_instance['LicenseModel'],
                                                  StorageType=source_instance['StorageType'],
                                                  DBParameterGroupName=source_instance['DBParameterGroups'][0]['DBParameterGroupName']
                                                )
            print(str(instance_response))
            #    wait_for_single_instance_to_be_ready(client, instance_response)
            #    print("  Adding writer instances to RDS cluster completed...")
                
            #if member['IsClusterWriter']==False:
            #    print("Reader Node")
                
        
    return {
        'statusCode': status_code,
        'isBase64Encoded': False,
        'headers': {"Content-Type":"application/json"},
        'body': json.dumps({'message': status_message})
    }

def wait_for_snapshot_to_be_ready(rds_client, snapshot):

    # simply check if the specified snapshot is healthy every 5 seconds until it
    # is
    while True:
        snapshotcheck = rds_client.describe_db_cluster_snapshots(DBClusterIdentifier=snapshot['DBClusterIdentifier'], DBClusterSnapshotIdentifier=snapshot['DBClusterSnapshotIdentifier'])['DBClusterSnapshots'][0]
        if snapshotcheck['Status'] == 'available':
            print("  Snapshot {} complete and available!".format(snapshot['DBClusterSnapshotIdentifier']))
            break
        else:
            print("Snapshot {} in progress, {}% complete".format(snapshot['DBClusterSnapshotIdentifier'], snapshotcheck['PercentProgress']))
            time.sleep(10)
            
def wait_for_instance_to_be_ready(rds_client, instance):
	# simply check if the specified instance is healthy every 5 seconds until it
	# is
	while True:
		instancecheck = rds_client.describe_db_clusters(DBClusterIdentifier=instance['DBCluster']['DBClusterIdentifier'])
		print(str(instancecheck))
		if instancecheck['DBClusters'][0]['Status'] == 'available':
			print("  Instance {} ready and available!".format(instance['DBCluster']['DBClusterIdentifier']))
			break
		else:
			print("Instance creation in progress, sleeping 10 seconds...")
			time.sleep(10)

def wait_for_single_instance_to_be_ready(rds_client, instance):
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
