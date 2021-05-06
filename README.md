# AWS KMS Encryption

1. Aurora RDS Encryption: </br>
   - Check source Aurora cluster is exist or not</br>
   - Create the snapshot of existing Aurora cluster with current date </br>
   - Restore new Aurora DB cluster with newly created snapshotand KMS key </br>
   - Wait for New Aurora DB is up and running </br>
   - Create new DB instance i.e. Write by copying all the configurations from source DB instance  </br>
   - Exit the execution without waiting for completion of write and reader to up and running since its takes too much time </br>
   - Wait for completion of writer and reader replica to be up and running </br>
   
2. Volume Encryption: </br>
   - Stop EC2 instance </br>
   - Create new EBS snashot for volumns attached to EC2 </br>
   - Create new EBS volume with same existing volumn properties like availability zone, tags etc.. with new KMS encryption key </br>
   - Deattach existing volume </br>
   - Attach new encrypted volume </br>
   
3. Elasticsearch Service Encryption: </br>
   - Create new elasticsearch domain by copying existing ES domain properties like availability zone, tags and other settings with new KMS encryption key </br>
   - Create snapshot of existing ES domain indexes to S3 </br>
   - Restore snapshot to newly created ES domain </br>

4. S3 Bucket Encryption: </br>
   - Find S3 bucket </br>
   - Change KMS encryption key </br>
