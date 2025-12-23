import os
import uuid
from datetime import datetime
import boto3
import json
import requests

# Initialize clients and variables in global scope
DYNAMODB = boto3.resource('dynamodb')

# Get configuration from environment variables
WAITING_ROOM_TABLE_NAME = os.environ.get('WAITING_ROOM_TABLE')
CHATROOMS_TABLE_NAME = os.environ.get('CHATROOMS_TABLE')
APPSYNC_URL = os.environ.get('APPSYNC_URL')
APPSYNC_API_KEY = os.environ.get('APPSYNC_API_KEY')

def handler(event, context):
    """
    Triggered by DynamoDB Stream when players join waiting room.
    """
    print("DynamoDB Stream event received:", event)
    
    try:
        waiting_room_table = DYNAMODB.Table(WAITING_ROOM_TABLE_NAME)
        chatrooms_table = DYNAMODB.Table(CHATROOMS_TABLE_NAME)
        
        response = waiting_room_table.scan(Select='COUNT')
        player_count = response['Count']
        
        print(f"Current players in waiting room: {player_count}")
        
        if player_count >= 2:
            players_response = waiting_room_table.scan(Limit=2)
            players = players_response.get('Items', [])
            
            if len(players) >= 2:
                player1 = players[0]
                player2 = players[1]
                ai_participant_id = f"ai-{str(uuid.uuid4())}"
                chatroom_id = str(uuid.uuid4())

                print(f"Matching players {player1['id']} and {player2['id']}")

                chatrooms_table.put_item(
                    Item={
                        'id': chatroom_id,
                        'participants': [player1['id'], player2['id'], ai_participant_id],
                        'createdAt': datetime.utcnow().isoformat() + "Z"
                    }
                )

                with waiting_room_table.batch_writer() as batch:
                    batch.delete_item(Key={'id': player1['id']})
                    batch.delete_item(Key={'id': player2['id']})
                
                # --- THIS IS THE FIX ---
                # Notify both players, passing the other player's ID to the function.
                notify_player_match(player1['id'], player2['id'], chatroom_id)
                notify_player_match(player2['id'], player1['id'], chatroom_id)
                # --- END OF FIX ---
                
                print(f"Chatroom {chatroom_id} created and notifications sent.")
        
        else:
            print(f"Not enough players ({player_count}), waiting for more...")
            
    except Exception as e:
        print(f"Error during matchmaking: {e}")
        raise e
    
def notify_player_match(user_id_to_notify, other_player_id, chatroom_id):
    """
    Calls the createMatch GraphQL mutation, providing both the recipient's ID
    and the ID of the player they were matched with.
    """
    try:
        mutation = """
          mutation CreateMatch($userId: ID!, $matchedUserId: ID!, $chatroomId: ID!) {
            createMatch(userId: $userId, matchedUserId: $matchedUserId, chatroomId: $chatroomId) {
              userId
              chatroomId
              matchedUserId
            }
          }
        """
        payload = {
            "query": mutation,
            "variables": {
                "userId": user_id_to_notify,
                "matchedUserId": other_player_id,
                "chatroomId": chatroom_id
            }
        }
        
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': APPSYNC_API_KEY
        }
        
        print(f"Sending request for user {user_id_to_notify} matched with {other_player_id}")
        response = requests.post(APPSYNC_URL, json=payload, headers=headers)
        response.raise_for_status()
        
        print(f"Successfully notified player {user_id_to_notify}: {response.text}")
        
    except Exception as e:
        print(f"Error notifying player {user_id_to_notify} via AppSync: {e}")