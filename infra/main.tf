terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.79"
    }
  }
}

provider "aws" {
  region = "us-east-2"
}

resource "aws_iam_role" "s3_role" {
  name = "lambda-s3-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role" "s3_polly_role" {
  name = "polly-s3-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "polly.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "s3_policy" {
  name = "S3AccessPolicy"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid     = "AllowS3Actions"
        Action = [
          "s3:PutObject",
        ]
        Effect   = "Allow"
        Resource = "arn:aws:s3:::files-mikeg/*"
      }
    ]
  })
}

resource "aws_iam_policy" "s3_polly_policy" {
  name = "PollyS3AccessPolicy"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowS3ActionsForPolly",
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject",
        ]
        Effect   = "Allow"
        Resource = [
          "arn:aws:s3:::files-mikeg",
          "arn:aws:s3:::files-mikeg/*"
        ]
      },
      {
        Sid    = "AllowPollyActions",
        Effect = "Allow",
        Action = [
          "polly:SynthesizeSpeech"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "s3_role_attachment" {
  role       = aws_iam_role.s3_role.name
  policy_arn = aws_iam_policy.s3_policy.arn
}

resource "aws_iam_role_policy_attachment" "s3_polly_role_attachment" {
  role       = aws_iam_role.s3_polly_role.name
  policy_arn = aws_iam_policy.s3_polly_policy.arn
}

resource "aws_s3_bucket" "pollybucket" {
  bucket = "files-mikeg"
}

resource "aws_s3_object" "files_folder" {
  bucket = aws_s3_bucket.pollybucket.id 
  key    = "files/"
  content = ""
}

resource "aws_s3_object" "polly_files" {
  bucket = aws_s3_bucket.pollybucket.id
  key    = "tts/"
  content = ""
}

resource "aws_lambda_function" "lambda_files" {
  function_name = "UploadFiles"
  role        = aws_iam_role.s3_role.arn
  handler     = "upload.main_handler"
  runtime     = "python3.12"

  filename    = "lambda-dummy.zip"
  source_code_hash = filebase64sha256("lambda-dummy.zip")

  timeout = 30
}

resource "aws_lambda_function" "lambda_polly" {
  function_name = "PollySynthesize"
  role          = aws_iam_role.s3_polly_role.arn
  handler       = "event.lambda_handler"
  runtime       = "python3.12"

  filename      = "lambda-dummy.zip"
  source_code_hash = filebase64sha256("lambda-dummy.zip")

  timeout = 30
}

resource "aws_s3_bucket_notification" "lambda_trigger" {
  bucket = aws_s3_bucket.pollybucket.id

  lambda_function {
    events = ["s3:ObjectCreated:*"]
    filter_prefix = "files/"
    lambda_function_arn = aws_lambda_function.lambda_polly.arn
  }

  depends_on = [
    aws_lambda_permission.allow_s3_invoke
  ]
}

resource "aws_lambda_permission" "allow_s3_invoke" {
  statement_id  = "AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda_polly.function_name
  principal     = "s3.amazonaws.com"

  source_arn = aws_s3_bucket.pollybucket.arn
}

resource "aws_api_gateway_rest_api" "upload_api" {
  name        = "UploadAPI"
  description = "API Gateway pointing to UploadFiles Lambda"
}

resource "aws_api_gateway_resource" "upload_resource" {
  rest_api_id = aws_api_gateway_rest_api.upload_api.id
  parent_id   = aws_api_gateway_rest_api.upload_api.root_resource_id
  path_part   = "upload"
}

resource "aws_api_gateway_method" "post_upload" {
  rest_api_id   = aws_api_gateway_rest_api.upload_api.id
  resource_id   = aws_api_gateway_resource.upload_resource.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id = aws_api_gateway_rest_api.upload_api.id
  resource_id = aws_api_gateway_resource.upload_resource.id
  http_method = aws_api_gateway_method.post_upload.http_method
  type        = "AWS_PROXY"
  integration_http_method = "POST"
  uri         = aws_lambda_function.lambda_files.invoke_arn
}

resource "aws_lambda_permission" "apigw_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda_files.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.upload_api.execution_arn}/*/*"
}

resource "aws_api_gateway_deployment" "upload_deployment" {
  depends_on = [aws_api_gateway_integration.lambda_integration]
  rest_api_id = aws_api_gateway_rest_api.upload_api.id
}
