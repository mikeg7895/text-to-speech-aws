import boto3
import base64
import json
import uuid
from datetime import datetime

s3 = boto3.client('s3')
bucket_name = 'files-mikeg'

def lambda_handler(event, context):
    try:
        body = event.get('body', '')
        if not body:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No body found in request'}),
                'headers': {'Content-Type': 'application/json'}
            }
        
        if event.get('isBase64Encoded', False):
            try:
                body = base64.b64decode(body)
                 
            except Exception as e:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid base64 encoding'}),
                    'headers': {'Content-Type': 'application/json'}
                }
        else:
            body = body.encode('utf-8') if isinstance(body, str) else body        
        headers = {k.lower(): v for k, v in event.get('headers', {}).items()}
        content_type = headers.get('content-type', '')

        boundary = None
        if 'multipart/form-data' in content_type:
            boundary_parts = content_type.split('boundary=')
            if len(boundary_parts) > 1:
                boundary = boundary_parts[1].strip().strip('"')
            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'No boundary found in multipart data'}),
                    'headers': {'Content-Type': 'application/json'}
                }
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Content-Type must be multipart/form-data'}),
                'headers': {'Content-Type': 'application/json'}
            }
        
        body_str = body.decode('utf-8', errors='ignore')
        parts = body_str.split(f'--{boundary}')
        
        file_data = None
        filename = None
        
        for part in parts:
            if 'Content-Disposition' in part and 'filename=' in part:
                lines = part.split('\r\n')
                
                for line in lines:
                    if 'filename=' in line:
                        filename_match = line.split('filename=')[1].strip().strip('"')
                        if filename_match and filename_match != '':
                            filename = filename_match
                            break
                
                content_start = False
                file_content_lines = []
                for line in lines:
                    if content_start:
                        file_content_lines.append(line)
                    elif line.strip() == '':
                        content_start = True
                
                if file_content_lines:
                    file_data = '\r\n'.join(file_content_lines).rstrip(f'--{boundary}--').rstrip('\r\n')
                    break
        
        if not filename or not file_data:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'No file found or file is empty',
                    'filename': filename,
                    'has_data': bool(file_data)
                }),
                'headers': {'Content-Type': 'application/json'}
            }
        
        allowed_extensions = ['.txt', '.csv', '.json', '.xml', '.log', '.md', '.yaml', '.yml', '.ini', '.cfg', '.conf']
        file_extension = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
        
        if file_extension not in allowed_extensions:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': f'File type not allowed. Allowed types: {", ".join(allowed_extensions)}',
                    'filename': filename,
                    'extension': file_extension
                }),
                'headers': {'Content-Type': 'application/json'}
            }
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        unique_filename = f"{timestamp}_{unique_id}_{filename}"
        
        content_type_map = {
            '.txt': 'text/plain',
            '.csv': 'text/csv',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.log': 'text/plain',
            '.md': 'text/markdown',
            '.yaml': 'application/x-yaml',
            '.yml': 'application/x-yaml',
            '.ini': 'text/plain',
            '.cfg': 'text/plain',
            '.conf': 'text/plain'
        }
        
        s3_content_type = content_type_map.get(file_extension, 'text/plain')
        
        s3.put_object(
            Bucket=bucket_name,
            Key=unique_filename,
            Body=file_data.encode('utf-8'),
            ContentType=s3_content_type,
            Metadata={
                'original-filename': filename,
                'upload-timestamp': timestamp,
                'file-extension': file_extension
            }
        )
        
        print(f"Successfully uploaded {unique_filename} to S3")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'File uploaded successfully',
                'original_filename': filename,
                's3_key': unique_filename,
                'size': len(file_data),
                'content_type': s3_content_type,
                'upload_timestamp': timestamp
            }),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            }
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Internal server error: {str(e)}',
                'type': 'server_error'
            }),
            'headers': {'Content-Type': 'application/json'}
        }

def handle_options():
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '86400'
        }
    }

def main_handler(event, context):
    if event.get('httpMethod') == 'OPTIONS':
        return handle_options()
    else:
        return lambda_handler(event, context)
