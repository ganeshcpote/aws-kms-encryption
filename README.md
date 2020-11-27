# AWS KMS Encryption

1. Aurora RDS Encryption: </br>
   a. Check source Aurora cluster is exist or not</br>
   b. Create the snapshot of existing Aurora cluster with current date </br>
   c. Restore new Aurora DB cluster with newly created snapshotand KMS key </br>
   d. Wait for New Aurora DB is up and running </br>
   e. Create new DB instance i.e. Write by copying all the configurations from source DB instance  </br>
   f. Exit the execution without waiting for completion of write and reader to up and running since its takes too much time </br>
   g. Wait for completion of writer and reader replica to be up and running </br>
   
2. Volume Encryption: </br>
   a. Stop EC2 instance </br>
   b. Create new EBS snashot for volumns attached to EC2 </br>
   c. Create new EBS volume with same existing volumn properties like availability zone, tags etc.. with new KMS encryption key </br>
   d. Deattach existing volume </br>
   e. Attach new encrypted volume </br>
   
 3. Elasticsearch Service Encryption: </br>
   a. Create new elasticsearch domain by copying existing ES domain properties like availability zone, tags and other settings with new KMS encryption key </br>
   b. create snapshot of existing ES domain indexes to S3 </br>
   c. restore snapshot to newly created ES domain </br>
