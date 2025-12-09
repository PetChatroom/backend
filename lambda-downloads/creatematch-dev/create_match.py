import json
import boto3

dynamodb = boto3.resource('dynamodb')

def handler(event, context):
    print("createMatch event:", event)
    
    try:
        args = event['arguments']
        user_id_to_notify = args['userId']
        the_other_player_id = args['matchedUserId'] # <-- Get the new argument
        chatroom_id = args['chatroomId']
        
        print(f"Processing match for user {user_id_to_notify} with {the_other_player_id}")
        
        response_payload = {
            'userId': user_id_to_notify,
            'matchedUserId': the_other_player_id, # <-- Use the correct value
            'chatroomId': chatroom_id
        }

        print(f"Returning payload to AppSync: {json.dumps(response_payload)}")
        
        return response_payload
        
    except Exception as e:
        print(f"Error in createMatch: {e}")
        raise e