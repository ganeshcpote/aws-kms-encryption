import json
import sys
import boto3
import botocore
import argparse

def lambda_handler(event, context):
    print(str(event))
    inputParam = json.loads(event['body'])
    instance_id = inputParam['instance_id']
    customer_master_key = inputParam['customer_master_key']
    region = inputParam['region']
    
    return encrypt_volume(instance_id, customer_master_key, region)

def encrypt_volume(instance_id, customer_master_key, region):
    print('Instance ID : {}'.format(instance_id))
    print('KmsKey ID : {}'.format(customer_master_key))
    print('Region : {}'.format(region))

    client = boto3.client('ec2', region_name=region)
    ec2 = boto3.client('ec2', region_name=region)
    ec2_resource = boto3.resource('ec2')
    
    waiter_instance_exists = client.get_waiter('instance_exists')
    waiter_instance_stopped = client.get_waiter('instance_stopped')
    waiter_instance_running = client.get_waiter('instance_running')
    waiter_snapshot_complete = client.get_waiter('snapshot_completed')
    waiter_volume_available = client.get_waiter('volume_available')
    
    print('---Checking instance ({})'.format(instance_id))

    try:
        waiter_instance_exists.wait(
            InstanceIds=[
                instance_id,
            ]
        )
    except botocore.exceptions.WaiterError as e:
        sys.exit('EC2 ERROR: {}'.format(e))

    all_mappings = []    
    
    instance = ec2_resource.Instance(instance_id)
    block_device_mappings = instance.block_device_mappings

    for device_mapping in block_device_mappings:
        original_mappings = {
            'DeleteOnTermination': device_mapping['Ebs']['DeleteOnTermination'],
            'VolumeId': device_mapping['Ebs']['VolumeId'],
            'DeviceName': device_mapping['DeviceName'],
        }
        all_mappings.append(original_mappings)
  
    volume_data = []
    
    print('---Preparing instance')    
    """ Get volume and exit if already encrypted """
    volumes = [v for v in instance.volumes.all()]

    print('---There are {0} volumns attached to Ec2 : {1}'. format(len(volumes),str(volumes)))
    
    for volume in volumes:
        print('---Encryption process started for volumn {}'.format(str(volume.volume_id)))
        volume_encrypted = volume.encrypted
        
        current_volume_data = {}
        for mapping in all_mappings:
            if mapping['VolumeId'] == volume.volume_id:
                current_volume_data = {
                    'volume': volume,
                    'DeleteOnTermination': mapping['DeleteOnTermination'],
                    'DeviceName': mapping['DeviceName'],
                }        

        """ Step 1: Prepare instance """
    
        # Exit if instance is pending, shutting-down, or terminated
        instance_exit_states = [0, 32, 48]
        if instance.state['Code'] in instance_exit_states:
            sys.exit(
                'ERROR: Instance is {} please make sure this instance is active.'
                .format(instance.state['Name'])
            )
    
        # Validate successful shutdown if it is running or stopping
        if instance.state['Code'] == 16:
            instance.stop()
    
        # Set the max_attempts for this waiter (default 40)
        waiter_instance_stopped.config.max_attempts = 80
    
        try:
            waiter_instance_stopped.wait(
                InstanceIds=[
                    instance_id,
                ]
            )
        except botocore.exceptions.WaiterError as e:
            sys.exit('ERROR: {}'.format(e))
    
        """ Step 2: Take snapshot of volume """
        print('-----Create snapshot of volume ({})'.format(volume.id))
        snapshot = ec2.create_snapshot(
            VolumeId=volume.id,
            Description='Snapshot of volume ({})'.format(volume.id),
        )

        snapshot_id = snapshot['SnapshotId']

        print(str(snapshot))
        print(str(snapshot_id))
        
        waiter_snapshot_complete.config.max_attempts = 240
    
        try:
            waiter_snapshot_complete.wait(
                SnapshotIds=[
                    snapshot_id,
                ]
            )
        except botocore.exceptions.WaiterError as e:
            snapshot.delete()
            sys.exit('ERROR: {}'.format(e))
    
        """ Step 3: Create encrypted volume """    
        print('-----Create encrypted volume from snapshot')
        print(str(volume.tags))
        tag_list = volume.tags

        if volume.volume_type == 'io1':
            volume_encrypted = ec2.create_volume(
                SnapshotId=snapshot_id,
                Encrypted=True,
                KmsKeyId=customer_master_key,
                VolumeType=volume.volume_type,
                Iops=volume.iops,
                AvailabilityZone=instance.placement['AvailabilityZone']
            )
        else:
            volume_encrypted = ec2.create_volume(
                SnapshotId=snapshot_id,
                Encrypted=True,
                KmsKeyId=customer_master_key,
                VolumeType=volume.volume_type,
                AvailabilityZone=instance.placement['AvailabilityZone']
            )
        
        print("volume_encrypted " + str(volume_encrypted))
        print("volume " + str(volume.tags))
        _volume_encrypted = ec2_resource.Volume(volume_encrypted['VolumeId'])
        print(str(_volume_encrypted))

        # Add original tags to new volume 
        if volume.tags:
            _volume_encrypted.create_tags(Tags=volume.tags)
    
        """ Step 4: Detach current volume """
        print('-----Detach volume {}'.format(volume.id))
        instance.detach_volume(
            VolumeId=volume.id,
            Device=current_volume_data['DeviceName']
        )
    
        """ Step 5: Attach new encrypted volume """
        print('-----Attach volume {}'.format(volume_encrypted['VolumeId']))
        try:
            waiter_volume_available.wait(
                VolumeIds=[
                    volume_encrypted['VolumeId'],
                ],
            )
        except botocore.exceptions.WaiterError as e:
            snapshot.delete()
            volume_encrypted.delete()
            sys.exit('ERROR: {}'.format(e))
    
        instance.attach_volume(
            VolumeId=volume_encrypted['VolumeId'],
            Device=current_volume_data['DeviceName']
        )
        
        current_volume_data['snapshot'] = snapshot
        current_volume_data['volume_encrypted'] = volume_encrypted
        volume_data.append(current_volume_data)                  
    
    for bdm in volume_data:
        # Modify instance attributes
        instance.modify_attribute(
            BlockDeviceMappings=[
                {
                    'DeviceName': bdm['DeviceName'],
                    'Ebs': {
                        'DeleteOnTermination':
                        bdm['DeleteOnTermination'],
                    },
                },
            ],
        )
    """ Step 6: Start instance """
    print('---Start instance')
    instance.start()
    try:
        waiter_instance_running.wait(
            InstanceIds=[
                instance_id,
            ]
        )
    except botocore.exceptions.WaiterError as e:
        sys.exit('ERROR: {}'.format(e))

    """ Step 7: Clean up """
    #print('---Clean up resources')
    #print(str(volume_data))
    #for cleanup in volume_data:
    #    print('---Remove snapshot {}'.format(cleanup['snapshot']['SnapshotId']))
    #    ec2_resource.Snapshot(cleanup['snapshot']['SnapshotId']).delete()
        
    #    print('---Remove original volume {}'.format(cleanup['snapshot']['VolumeId']))
    #    ec2_resource.Volume(cleanup['snapshot']['VolumeId']).delete()

    """ Step 8: Clean up """
    print('---Printing information')

    for cleanup in volume_data:
        print('  original volume {}'.format(cleanup['snapshot']['VolumeId']))
        print('  snapshot {}'.format(cleanup['snapshot']['SnapshotId']))
        print('  new encrypted volume {}'.format(cleanup['volume_encrypted']['VolumeId']))
    
    response = {}
    _encrypt_volumes = [v['volume_encrypted']['VolumeId'] for v in volume_data]
    response['instanceId'] = instance_id
    response['encrypted_volumes'] = _encrypt_volumes
    response['statusCode'] = 200

    print('Encryption finished')
    return json.dumps(response)