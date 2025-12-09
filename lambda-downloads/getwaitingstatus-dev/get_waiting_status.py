import json
import os
import boto3

dynamodb = boto3.resource('dynamodb')

def handler(event, context):
    user_id = event['arguments']['userId']
    
    try:
        WAITING_TABLE = os.environ.get('WAITING_ROOM_TABLE')
        CHATROOMS_TABLE = os.environ.get('CHATROOMS_TABLE')
        
        waiting_table = dynamodb.Table(WAITING_TABLE)
        chatrooms_table = dynamodb.Table(CHATROOMS_TABLE)
        
        # Check if user is in waiting room
        waiting_response = waiting_table.get_item(Key={'id': user_id})
        
        if 'Item' in waiting_response:
            return {
                'userId': user_id,
                'status': 'waiting',
                'chatroomId': None,
                'waitTime': 0
            }
        else:
            # Check if user is in any chatroom
            # This assumes your chatrooms table has a 'participants' attribute
            chatroom_response = chatrooms_table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('participants').contains(user_id)
            )
            
            if chatroom_response['Items']:
                # User is in a chatroom
                chatroom = chatroom_response['Items'][0]
                return {
                    'userId': user_id,
                    'status': 'matched',
                    'chatroomId': chatroom['id'],
                    'waitTime': 0
                }
            else:
                # User not found anywhere
                return {
                    'userId': user_id,
                    'status': 'not_found',
                    'chatroomId': None,
                    'waitTime': 0
                }
            
    except Exception as e:
        print(f"Error: {e}")
        return {
            'userId': user_id,
            'status': 'error',
            'chatroomId': None,
            'waitTime': 0
        }