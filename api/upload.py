import boto3
import base64
import json
import uuid
from datetime import datetime
import cgi
from io import BytesIO

s3 = boto3.client('s3')
bucket_name = 'files-mikeg'

def lambda_handler(event, context):
    try:
        print(f"Event received: {json.dumps(event, default=str)}")
        
        # Get the body
        body = event.get('body', '')
        if not body:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No body found in request'}),
                'headers': {'Content-Type': 'application/json'}
            }
        
        # Handle base64 encoded body - Fixed boolean conversion
        is_base64_encoded = event.get('isBase64Encoded')
        if is_base64_encoded is True or (isinstance(is_base64_encoded, str) and is_base64_encoded.lower() == 'true'):
            try:
                body = base64.b64decode(body)
                print("Successfully decoded base64 body")
            except Exception as e:
                print(f"Failed to decode base64: {e}")
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid base64 encoding'}),
                    'headers': {'Content-Type': 'application/json'}
                }
        else:
            body = body.encode('utf-8') if isinstance(body, str) else body
        
        # Get headers with better error handling
        headers = event.get('headers', {})
        if not isinstance(headers, dict):
            headers = {}
        
        headers = {k.lower(): v for k, v in headers.items()}
        content_type = headers.get('content-type', '')
        
        print(f"Content-Type: {content_type}")
        print(f"Body length: {len(body)}")
        
        # Validate content type
        if not content_type.startswith('multipart/form-data'):
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Content-Type must be multipart/form-data, got: {content_type}'}),
                'headers': {'Content-Type': 'application/json'}
            }
        
        # Create file-like object for cgi.FieldStorage
        fp = BytesIO(body)
        
        # Create environment for cgi.FieldStorage
        environ = {
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': content_type,
            'CONTENT_LENGTH': str(len(body)),
        }
        
        # Parse with cgi.FieldStorage
        try:
            form = cgi.FieldStorage(fp=fp, environ=environ)
        except Exception as e:
            print(f"Error parsing form data: {e}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Failed to parse form data: {str(e)}'}),
                'headers': {'Content-Type': 'application/json'}
            }
        
        # Find the file field
        file_field = None
        if hasattr(form, 'list') and form.list:
            for field in form.list:
                if hasattr(field, 'filename') and field.filename:
                    file_field = field
                    break
        
        if file_field is None:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No file found in request'}),
                'headers': {'Content-Type': 'application/json'}
            }
        
        # Get file data
        filename = file_field.filename
        file_content = file_field.value
        
        print(f"Original filename: {filename}")
        print(f"File content length: {len(file_content) if file_content else 0}")
        
        # Validate file
        if not filename or not file_content:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'File is empty or has no name'}),
                'headers': {'Content-Type': 'application/json'}
            }
        
        # Create unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        unique_filename = f"{timestamp}_{unique_id}_{filename}"
        
        # Determine content type based on file extension
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
            '.conf': 'text/plain',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        
        file_extension = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
        s3_content_type = content_type_map.get(file_extension, 'application/octet-stream')
        
        # Handle text files - ensure they're properly encoded
        if isinstance(file_content, str):
            file_content = file_content.encode('utf-8')
        
        # Upload to S3
        s3.put_object(
            Bucket=bucket_name,
            Key=f"files/{unique_filename}",
            Body=file_content,
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
                's3_key': f"files/{unique_filename}",
                'size': len(file_content),
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
                'type': 'server_error',
                'details': traceback.format_exc()
            }),
            'headers': {'Content-Type': 'application/json'}
        }

# Handle OPTIONS for CORS
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

# Main handler
def main_handler(event, context):
    try:
        http_method = event.get('httpMethod', '').upper()
        if http_method == 'OPTIONS':
            return handle_options()
        else:
            return lambda_handler(event, context)
    except Exception as e:
        print(f"Error in main_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Handler error: {str(e)}',
                'type': 'handler_error'
            }),
            'headers': {'Content-Type': 'application/json'}
        }
