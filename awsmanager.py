from http.client import responses

import boto3
import logging
import os
import json
import datetime

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

    def describe_instances(self, instance_id):
        response = self.ec2.describe_instances(InstanceIds=[instance_id])
        self.logging.info(json.dumps(response, indent=2, default=str))

    def create_instance(self, ami, instance_type, key_name, security_group_ids, subnet_id):
        response = {}
        try:
            self.logging.info("Trying to create instances.")
            response = self.ec2.run_instances(
                ImageId=ami,
                InstanceType=instance_type,
                SubnetId=subnet_id,
                KeyName=key_name,
                SecurityGroupIds=security_group_ids,
                MinCount=3,
                MaxCount=3,
            )
            self.logging.info("Instances created successfully.")
        except Exception as e:
            self.logging.critical(f"Unable to create instance.")
            self.logging.info(f"error: {e}")
        try:
            self.logging.info("Trying to tag instances.")
            instances_ids = [i["InstanceId"] for i in response["Instances"]]
            for idx, instance_id in enumerate(instances_ids, start=1):
                self.ec2.create_tags(
                    Resources=[instance_id],
                    Tags=[
                        {"Key": "Name", "Value": f"{os.getlogin()}-{idx}"},
                        {"Key": "Creation_Date", "Value": datetime.datetime.now().strftime('%Y-%m-%d')},
                        {"Key": "Creation_Time", "Value": datetime.datetime.now().strftime('%H:%M:%S')},
                        {"Key": "TTL", "Value": 3},
                        {"Key": "Owner", "Value": os.getlogin()}
                    ]
                )
            self.logging.info("Tags created successfully.")
        except Exception as e:
            self.logging.critical(f"Unable to tag instance.")
            self.logging.info(f"error: {e}")


if __name__ == "__main__":
    aws = AWSManager("il-central-1")
    aws.ec2.create_instance('ami-04dbb447f35f57d09', "t3.micro", "Liel", ["sg-0b2d91c761e623f65"],
                            "subnet-09a20cbde1d2c0c16")
