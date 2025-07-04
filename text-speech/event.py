import boto3
from datetime import datetime 

s3 = boto3.client('s3')
polly = boto3.client('polly')

def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        try:
            response = s3.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')

            response_polly = polly.synthesize_speech(
                Text=content,
                OutputFormat='mp3',
                VoiceId='Joanna',
                LanguageCode='en-US'
            )

            filename = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            s3.put_object(
                Bucket=bucket,
                Key=f'tts/{filename}.mp3',
                Body=response_polly['AudioStream'].read(),
                ContentType='audio/mpeg'
            )
        except Exception as e:
            print(f"Error getting object {key} from bucket {bucket}: {e}")
