import json
import os
import boto3

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('WAITING_ROOM_TABLE')
table = dynamodb.Table(TABLE_NAME)

def handler(event, context):
    user_id = event['arguments']['userId']
    
    try:
        # Remove user from waiting room
        table.delete_item(Key={'id': user_id})
        
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False