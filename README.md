# AWS KMS Encryption


1. Aurora RDS Encryption:
   a. Check source Aurora cluster is exist or not
   b. Create the snapshot of existing Aurora cluster with current date i.e.mst-rds-devprv-cluster-2020-11-19 
   c. Restore new Aurora DB cluster with newly created snapshotand KMS key
   d. Wait for New Aurora DB is up and running
   e. Create new DB instance i.e. Write by copying all the configurations from source DB instance 
   f. Exit the execution without waiting for completion of write and reader to up and running since its takes too much time
   g. Wait for completion of writer and reader replica to be up and running
   
2. Volume Encryption:
   a. Stop EC2 instance
   b. Create new EBS snashot for volumns attached to EC2
   c. Create new EBS volume with same existing volumn properties like availability zone, tags etc.. with new KMS encryption key
   d. Deattach existing volume
   e. Attach new encrypted volume
   
 3. Elasticsearch Service Encryption:
   a. Create new elasticsearch domain by copying existing ES domain properties like availability zone, tags and other settings with new KMS encryption key
   b. create snapshot of existing ES domain indexes to S3
   c. restore snapshot to newly created ES domain
