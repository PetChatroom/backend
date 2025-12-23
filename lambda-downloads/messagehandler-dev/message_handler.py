import json
import os
import uuid
from datetime import datetime
import boto3

# Initialize Boto3 clients in the global scope
DYNAMODB_RESOURCE = boto3.resource('dynamodb')
LAMBDA_CLIENT = boto3.client('lambda')

try:
    MESSAGES_TABLE_NAME = os.environ['MESSAGES_TABLE']
    # Get the AI Lambda function name directly from environment variable
    AI_RESPONSE_LAMBDA_NAME = os.environ['AI_RESPONSE_LAMBDA_NAME']
    print(f"Environment variables loaded: MESSAGES_TABLE={MESSAGES_TABLE_NAME}, AI_RESPONSE_LAMBDA_NAME={AI_RESPONSE_LAMBDA_NAME}")
except KeyError as e:
    print(f"FATAL: Missing required environment variable: {e}")
    raise e

# Get a reference to the DynamoDB table once
MESSAGES_TABLE = DYNAMODB_RESOURCE.Table(MESSAGES_TABLE_NAME)
print(f"DynamoDB table reference created: {MESSAGES_TABLE_NAME}")

def handler(event, context):
    """
    Handles the 'sendMessage' GraphQL mutation.
    """
    print(f"=== MESSAGE HANDLER STARTED ===")
    print(f"Received event from AppSync: {json.dumps(event)}")
    print(f"Context: {context}")

    try:
        # 1. PARSE ARGUMENTS
        args = event.get('arguments', {})
        chatroom_id = args.get('chatroomId')
        text = args.get('text')
        sender_id = args.get('senderId')
        
        print(f"Parsed arguments - chatroom_id: {chatroom_id}, text: {text}, sender_id: {sender_id}")

        if not all([chatroom_id, text, sender_id]):
            error_msg = "Missing required arguments: chatroomId, text, or senderId"
            print(f"ERROR: {error_msg}")
            raise ValueError(error_msg)

        message = {
            'id': str(uuid.uuid4()),
            'chatroomId': chatroom_id,
            'text': text,
            'senderId': sender_id,
            'createdAt': datetime.utcnow().isoformat() + "Z",
        }
        
        print(f"Created message object: {json.dumps(message)}")
    
        # 2. SAVE AND TRIGGER AI
        print(f"Attempting to save message to DynamoDB table: {MESSAGES_TABLE_NAME}")
        MESSAGES_TABLE.put_item(Item=message)
        print(f"Successfully saved message {message['id']} to chatroom {chatroom_id}")
        
        if not sender_id.startswith('ai-'):
            print(f"Human message received. Preparing to trigger AI response lambda: {AI_RESPONSE_LAMBDA_NAME}")
            
            ai_payload = {
                'chatroomId': chatroom_id,
                'chatHistory': [message]
            }
            
            print(f"AI payload: {json.dumps(ai_payload)}")
            print(f"Attempting to invoke Lambda: {AI_RESPONSE_LAMBDA_NAME}")
            print(f"Lambda client region: {LAMBDA_CLIENT.meta.region_name}")
            
            # Now attempt the invocation
            try:
                print("Attempting Lambda invoke...")
                response = LAMBDA_CLIENT.invoke(
                    FunctionName=AI_RESPONSE_LAMBDA_NAME,
                    InvocationType='Event',  # Async invocation
                    Payload=json.dumps(ai_payload)
                )
                
                print(f"Lambda invoke response: {response}")
                print(f"StatusCode: {response.get('StatusCode')}")
                print(f"FunctionError: {response.get('FunctionError')}")
                print(f"Payload: {response.get('Payload')}")
                print(f"ExecutedVersion: {response.get('ExecutedVersion')}")
                
                if response.get('StatusCode') == 202:
                    print("SUCCESS: Lambda invocation accepted (202 status)")
                else:
                    print(f"WARNING: Unexpected status code: {response.get('StatusCode')}")
                    
            except Exception as invoke_error:
                print(f"ERROR: Lambda invoke failed: {invoke_error}")
                print(f"Error type: {type(invoke_error)}")
                # Check for specific error types
                if hasattr(invoke_error, 'response'):
                    print(f"Error response: {invoke_error.response}")
                if hasattr(invoke_error, 'operation_name'):
                    print(f"Operation: {invoke_error.operation_name}")

        else:
            print("AI message detected, skipping AI response trigger")

        # 3. RETURN RESPONSE TO APPSYNC
        print(f"Returning message to AppSync: {json.dumps(message)}")
        return message

    except Exception as e:
        print(f"ERROR: Exception in handler: {e}")
        print(f"Exception type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise e

    finally:
        print("=== MESSAGE HANDLER COMPLETED ===")