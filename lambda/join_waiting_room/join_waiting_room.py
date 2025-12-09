import json
import os
import uuid
from datetime import datetime
import boto3

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('WAITING_ROOM_TABLE')
table = dynamodb.Table(TABLE_NAME)

def handler(event, context):
    # Generate a unique ID for the new participant
    user_id = str(uuid.uuid4())
    
    try:
        # Create the item to be stored in DynamoDB
        item = {
            'id': user_id,
            'createdAt': datetime.utcnow().isoformat() + "Z"
        }
        
        # Put the item into the waiting room table
        table.put_item(Item=item)
        
        # Return in GraphQL format
        return {
            'userId': user_id,
            'status': 'waiting',
            'chatroomId': None,
            'waitTime': 0
        }
        
    except Exception as e:
        print(f"Error: {e}")
        # Return error in expected format
        return {
            'userId': 'error',
            'status': 'error',
            'chatroomId': None,
            'waitTime': 0
        }