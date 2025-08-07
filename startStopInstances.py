import boto3 , argparse

def stop_ec2_instances(access_key, secret_key, region, instance_ids):
    try:
        ec2 = boto3.client(
            'ec2',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

        print(f"Stopping instances: {instance_ids}")
        response = ec2.stop_instances(InstanceIds=instance_ids)

        for instance in response['StoppingInstances']:
            print(f"Instance {instance['InstanceId']} is stopping. Current state: {instance['CurrentState']['Name']}")

    except Exception as e:
        print(f"Error: {e}")

def start_ec2_instances(access_key, secret_key, region, instance_ids):
    try:
        ec2 = boto3.client(
            'ec2',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

        print(f"Starting instances: {instance_ids}")
        response = ec2.start_instances(InstanceIds=instance_ids)

        for instance in response['StartingInstances']:
            print(f"Instance {instance['InstanceId']} is starting. Current state: {instance['CurrentState']['Name']}")

    except Exception as e:
        print(f"Error: {e}")        

if __name__ == "__main__":

    usage_msg = f"""\npython startStopInstances.py --region <region> --instances <instance1,instance2> --action <start | stop> --access_key <access_key> --secret_key <secret_key>\n"""
    parser = argparse.ArgumentParser(description="Enter Arguments")
    parser.add_argument("--region", type=str, required=True, help="Enter The Instances Region.")
    parser.add_argument("--instances", type=str, required=True, help="Enter The Instances ID.")
    parser.add_argument("--action", type=str, required=True, choices=["start", "stop"], help="Enter Action To Start Or Stop The Instances.")
    parser.add_argument("--access_key", type=str, required=True, help="Enter Access Key.")
    parser.add_argument("--secret_key", type=str, required=True, help="Enter Secret Key.")
    args = parser.parse_args()

    access_key = args.access_key
    secret_key = args.secret_key
    region = args.region
    instances = args.instances
    action = args.action

    AWS_ACCESS_KEY = access_key
    AWS_SECRET_KEY = secret_key
    REGION = region
    INSTANCE_IDS = instances.split(',')

    if action.lower() == "stop":
        stop_ec2_instances(AWS_ACCESS_KEY, AWS_SECRET_KEY, REGION, INSTANCE_IDS)

    if action.lower() == "start":
        start_ec2_instances(AWS_ACCESS_KEY, AWS_SECRET_KEY, REGION, INSTANCE_IDS)
