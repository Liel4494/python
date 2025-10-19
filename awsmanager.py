from datetime import datetime, timedelta
from xmlrpc.client import Boolean

import boto3
import logging
import os
import subprocess
import argparse

with open("AWS.log", 'w') as f:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename="AWS.log"
)


class AWSManager:
    def __init__(self, region):
        self.session = boto3.Session(
            region_name=region,
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            # aws_session_token=os.environ.get('AWS_SESSION_TOKEN'),
        )
        self.ec2 = EC2Manager(self.session)
        self.dynamo = DynamoBD(self.session)
        self.s3 = S3(self.session)


class EC2Manager:
    def __init__(self, session):
        self.ec2 = session.client('ec2')
        self.logging = logging.getLogger("EC2Manager")

    def start_instance(self, instance_id):
        try:
            self.logging.info(f"Trying to start instance {instance_id}.")
            instance_status = \
                self.ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0]["Instances"][0]["State"][
                    "Name"]
            if instance_status == "Stopped":
                self.ec2.start_instances(InstanceIds=[instance_id])
                self.logging.info(f"Instance {instance_id} started.")
            else:
                self.logging.info(f"Instance {instance_id} already started.")
        except Exception as e:
            self.logging.critical(f"Unable to start instance {instance_id}.")
            self.logging.info(f"error: {e}")

    def create_instance(self, count, ami, instance_type, key_name, security_group_ids, subnet_id):
        response = {}
        try:
            self.logging.info("Trying to create instances.")
            response = self.ec2.run_instances(
                ImageId=ami,
                InstanceType=instance_type,
                SubnetId=subnet_id,
                KeyName=key_name,
                SecurityGroupIds=security_group_ids,
                MinCount=count,
                MaxCount=count,
            )
            self.logging.info("Instances created successfully.")
        except Exception as e:
            self.logging.critical(f"Unable to create instance.")
            self.logging.info(f"error: {e}")
        try:
            self.logging.info("Trying to tag instances.")
            username = subprocess.run(["powershell", "-Command", "[Environment]::UserName"], capture_output=True,
                                      text=True,
                                      check=True).stdout.strip()
            instances_ids = [i["InstanceId"] for i in response["Instances"]]
            for idx, instance_id in enumerate(instances_ids, start=1):
                self.ec2.create_tags(
                    Resources=[instance_id],
                    Tags=[
                        {"Key": "Name", "Value": f"{os.getlogin()}-{idx}"},
                        {"Key": "Creation_Date", "Value": datetime.now().strftime('%d-%m-%Y')},
                        {"Key": "Creation_Time", "Value": datetime.now().strftime('%H:%M:%S')},
                        {"Key": "TTL", "Value": "3"},
                        {"Key": "Owner", "Value": username}
                    ]
                )
            self.logging.info("Tags created successfully.")
        except Exception as e:
            self.logging.critical(f"Unable to tag instance")
            self.logging.info(f"error: {e}")

    def check_ttl(self):
        for_delete_list = []
        now = datetime.now()
        try:
            self.logging.info("Check all instances TTL.")
            response = self.ec2.describe_instances(
                Filters=[
                    {
                        'Name': 'instance-state-name',
                        'Values': ['running']
                    },
                ]
            )
            for instance in response["Reservations"][0]["Instances"]:
                instance_id = instance["InstanceId"]
                tags = {t['Key']: t['Value'] for t in instance.get('Tags', [])}
                if not tags:
                    for_delete_list.append(instance_id)
                    self.logging.critical(f"Found instance without any tags - {instance_id} - adding to delete list.")

                creation_date = tags.get('Creation_Date')
                creation_time = tags.get('Creation_Time')
                ttl = int(tags.get('TTL'))

                created = datetime.strptime(f"{creation_date} {creation_time}", '%d-%m-%Y %H:%M:%S')
                expired_at = created + timedelta(minutes=ttl)
                if now > expired_at:
                    for_delete_list.append(instance_id)
                    self.logging.info(
                        f"Instance {instance_id} TTL has expired at {expired_at} - adding to delete list.")
            if for_delete_list:
                self.logging.info(f"New instances added to list 'for delete list', list: {for_delete_list}")
                current_list = aws.dynamo.get_for_delete_list()
                updated_list = list(set(for_delete_list + current_list))
                aws.dynamo.update_delete_list(updated_list)
            else:
                self.logging.info("No instances added to list 'for delete list' - The list is empty.")

        except Exception as e:
            self.logging.info("Unable to check instances TTL.")
            self.logging.info(f"error: {e}")

    def terminate_instance(self):
        try:
            self.logging.info(f"Delete expired instances")
            for_delete_list = aws.dynamo.get_for_delete_list()
            if for_delete_list:
                self.ec2.terminate_instances(InstanceIds=for_delete_list)
                self.logging.info(f"Instances {for_delete_list} terminated.")
                aws.dynamo.update_delete_list([])
            else:
                self.logging.info(f"There is no expired instance in the list")
        except Exception as e:
            self.logging.critical(f"Unable to terminate instances")
            self.logging.info(f"error: {e}")


class DynamoBD:
    def __init__(self, session):
        self.dynamo = session.resource('dynamodb')
        self.logging = logging.getLogger("DynamoBD")

    def get_for_delete_list(self, ):
        try:
            self.logging.info("Get 'for delete list' from DynamoDB.")
            table = self.dynamo.Table('For_Delete')
            current_list = table.get_item(Key={'delete_list': "instances_list"})['Item']['ids']
            self.logging.info(f"Current list: {current_list}")
            return current_list
        except Exception as e:
            self.logging.critical(f"Unable to get 'for delete list'")
            self.logging.info(f"error: {e}")

    def update_delete_list(self, updated_list):
        try:
            self.logging.info(f"Updating 'for delete list' with new list: {updated_list}")
            table = self.dynamo.Table('For_Delete')

            table.put_item(
                Item={
                    'delete_list': "instances_list",
                    'ids': updated_list
                }
            )
            current_list = table.get_item(Key={'delete_list': "instances_list"})['Item']['ids']
            self.logging.info(f"Updated list: {current_list}")
            self.logging.info("Update 'for delete list' succeeded.")
        except Exception as e:
            self.logging.critical(f"Unable to update delete list.")
            self.logging.info(f"error: {e}")


class S3:
    def __init__(self, session):
        self.s3 = session.client('s3')
        self.logging = logging.getLogger("S3")

    def upload_file(self, file_name, bucket, key):
        try:
            self.logging.info(f"Uploading {file_name} to {bucket}/{key}.")
            self.s3.upload_file(file_name, bucket, key)
        except Exception as e:
            self.logging.critical(f"Unable to upload file to S3.")
            self.logging.info(f"error: {e}")


if __name__ == "__main__":
    usage_msg = "\npython awsmanager.py --createInstances <True | False > --deleteExpired <True | False > --region <REGION> --count <NUMBER> --ttl <TIME_TO_LIVE>\n"
    parser = argparse.ArgumentParser(usage=usage_msg)
    parser.add_argument("--createInstances", help="Create Instances", type=Boolean, default=False)
    parser.add_argument("--deleteExpired", help="Delete expired instances", type=Boolean, default=False)
    parser.add_argument("--region", help="AWS region", default="il-central-1", required=False)
    parser.add_argument("--count", help="Instances Number", default="3", required=False, type=int)
    parser.add_argument("--ttl", help="Time To Live", default="3", required=False, type=int)

    args = parser.parse_args()
    create_instances = args.createInstances
    deleteExpired = args.deleteExpired
    region = args.region
    count = args.count
    ttl = args.ttl

    aws = AWSManager(region)
    if create_instances:
        aws.ec2.create_instance(count, 'ami-04dbb447f35f57d09', "t3.micro", "Liel", ["sg-0b2d91c761e623f65"],
                                "subnet-09a20cbde1d2c0c16")
    if deleteExpired:
        aws.ec2.check_ttl()
        aws.ec2.terminate_instance()

    aws.s3.upload_file('AWS.log', 'aws-manager-logs', 'logs/aws-manager.log')
