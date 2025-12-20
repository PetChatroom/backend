import boto3
import json
import os
import requests
import uuid
from datetime import datetime, timezone
import time
import random

# Initialize clients
DYNAMODB = boto3.resource('dynamodb')
SECRETS_MANAGER = boto3.client('secretsmanager')
SSM = boto3.client('ssm')

# Get environment variables
MESSAGES_TABLE_NAME = os.environ.get('MESSAGES_TABLE')
CHATROOMS_TABLE_NAME = os.environ.get('CHATROOMS_TABLE')
OPENAI_API_KEY_SECRET_NAME = os.environ.get('OPENAI_API_KEY_SECRET_NAME')
APPSYNC_URL = os.environ.get('APPSYNC_URL')
APPSYNC_API_KEY = os.environ.get('APPSYNC_API_KEY')
AI_PROMPT_PARAMETER_NAME = os.environ.get('AI_PROMPT_PARAMETER')

# Validate environment variables
if not AI_PROMPT_PARAMETER_NAME:
    raise ValueError("AI_PROMPT_PARAMETER environment variable is not set")

if not all([MESSAGES_TABLE_NAME, CHATROOMS_TABLE_NAME, OPENAI_API_KEY_SECRET_NAME, APPSYNC_URL, APPSYNC_API_KEY]):
    raise ValueError("One or more required environment variables are not set")

# Initialize tables
MESSAGES_TABLE = DYNAMODB.Table(MESSAGES_TABLE_NAME)
CHATROOMS_TABLE = DYNAMODB.Table(CHATROOMS_TABLE_NAME)

# --- CONFIGURATION FOR TYPING SIMULATION ---
TYPING_SPEED_CPS = 7
MIN_THINKING_SECONDS = 1.0
MAX_RANDOM_THINKING_SECONDS = 2.5
MAX_DELAY_SECONDS = 15  # IMPORTANT: Ensure your Lambda timeout is > this value

def get_openai_api_key():
    """Fetches the OpenAI API key from AWS Secrets Manager."""
    response = SECRETS_MANAGER.get_secret_value(SecretId=OPENAI_API_KEY_SECRET_NAME)
    secret = json.loads(response['SecretString'])
    return secret['openai_api_key']

def get_ai_prompt():
    """Fetches the AI prompt from SSM Parameter Store."""
    response = SSM.get_parameter(Name=AI_PROMPT_PARAMETER_NAME, WithDecryption=True)
    return response['Parameter']['Value']

def send_message_via_appsync(chatroom_id, text, sender_id):
    """Sends a message through AppSync to trigger subscriptions."""
    mutation = """
    mutation SendMessage($chatroomId: ID!, $text: String!, $senderId: String!) {
        sendMessage(chatroomId: $chatroomId, text: $text, senderId: $senderId) {
            id, chatroomId, text, senderId, createdAt
        }
    }
    """
    variables = {"chatroomId": chatroom_id, "text": text, "senderId": sender_id}
    response = requests.post(
        APPSYNC_URL,
        headers={'Content-Type': 'application/json', 'x-api-key': APPSYNC_API_KEY},
        json={'query': mutation, 'variables': variables},
        timeout=10
    )
    response.raise_for_status()
    return response.json()

def extract_output_text(resp_json: dict) -> str:
    """Extract text from the new Responses API output format."""
    parts = []
    for item in resp_json.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    parts.append(c.get("text", ""))
    return "".join(parts)

def handler(event, context):
    """Gets AI response and sends via AppSync after a simulated typing delay."""
    try:
        chatroom_id = event['chatroomId']
        
        OPENAI_API_KEY = get_openai_api_key()
        ai_prompt_content = get_ai_prompt()  # Get the AI prompt from SSM

        # Get chatroom details
        chatroom_response = CHATROOMS_TABLE.get_item(Key={'id': chatroom_id})
        if 'Item' not in chatroom_response:
            print("Chatroom not found.")
            return
        
        chatroom_item = chatroom_response['Item']
        ai_id = next((p for p in chatroom_item.get('participants', []) if p.startswith('ai-')), None)
        if not ai_id:
            print("AI participant not found in chatroom.")
            return

        # Get recent messages
        response = MESSAGES_TABLE.query(
            KeyConditionExpression='chatroomId = :cid',
            ExpressionAttributeValues={':cid': chatroom_id},
            Limit=30,
            ScanIndexForward=False
        )
        all_messages = sorted(response.get('Items', []), key=lambda x: x['createdAt'])
        
        # Check if AI was the last to speak
        if not all_messages or all_messages[-1]['senderId'].startswith('ai-'):
            print("No human messages to respond to or AI was the last to speak.")
            return
        
        # Check if there are multiple human messages since last AI response
        # Find the last AI message
        last_ai_index = -1
        for i in range(len(all_messages) - 1, -1, -1):
            if all_messages[i]['senderId'].startswith('ai-'):
                last_ai_index = i
                break
        
        # Get messages since last AI response
        messages_since_ai = all_messages[last_ai_index + 1:] if last_ai_index >= 0 else all_messages
        
        # Only respond if there's been enough human activity (at least 1 message from each human, or 2+ messages total)
        unique_human_senders = set(msg['senderId'] for msg in messages_since_ai if not msg['senderId'].startswith('ai-'))
        
        # If only one human has spoken once, wait for more conversation
        if len(messages_since_ai) < 2 and len(unique_human_senders) < 2:
            print(f"Waiting for more conversation activity. Only {len(messages_since_ai)} message(s) from {len(unique_human_senders)} human(s).")
            return

        # Prepare input for OpenAI Responses API
        input_items = []
        human_participant_names = {}
        player_counter = 1
        
        for msg in all_messages:
            sender_id = msg['senderId']
            if not sender_id.startswith('ai-') and sender_id not in human_participant_names:
                human_participant_names[sender_id] = f"Player_{player_counter}"
                player_counter += 1

        for msg in all_messages:
            sender_id = msg['senderId']
            role = "assistant" if sender_id.startswith('ai-') else "user"
            name = "AI_Player" if role == "assistant" else human_participant_names.get(sender_id, "Unknown_Player")
            input_items.append({"role": role, "name": name, "content": msg['text']})

        # Get AI response using new Responses API
        api_response = None
        try:
            api_response = requests.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-5.2",  # Using a valid model
                    "input": input_items,
                    "instructions": ai_prompt_content,
                    "temperature": 1.0,
                },
                timeout=30,
            )
            api_response.raise_for_status()
            response_data = api_response.json()
            ai_text = extract_output_text(response_data).strip()
            
            # Check if AI wants to remain silent
            if ai_text == "Silence1":
                print("AI chose to remain silent (Silence1). Not sending message.")
                return
            
            if not ai_text:
                print("OpenAI returned an empty response.")
                return

        except requests.exceptions.RequestException as e:
            print(f"OpenAI API error: {e}")
            if api_response is not None:
                print(f"Status: {api_response.status_code}, Response: {api_response.text}")
            return
            
        # Calculate and apply typing delay
        try:
            # 1. Calculate the time it would take to type the message
            typing_delay = len(ai_text) / TYPING_SPEED_CPS
            
            # 2. Calculate a random "thinking" time
            thinking_delay = MIN_THINKING_SECONDS + random.uniform(0, MAX_RANDOM_THINKING_SECONDS)
            
            # 3. Add them together to get the total delay
            total_delay = thinking_delay + typing_delay
            
            # 4. Cap the delay to prevent the Lambda from timing out
            if total_delay > MAX_DELAY_SECONDS:
                print(f"Calculated delay {total_delay:.2f}s is too long, capping at {MAX_DELAY_SECONDS}s.")
                total_delay = MAX_DELAY_SECONDS
                
            print(f"Simulating human response. Thinking: {thinking_delay:.2f}s, Typing: {typing_delay:.2f}s. Total Wait: {total_delay:.2f}s.")
            time.sleep(total_delay)

        except Exception as e:
            print(f"Error during delay calculation: {e}. Sending message immediately.")

        # Send response after delay
        try:
            send_message_via_appsync(chatroom_id, ai_text, ai_id)
            print(f"AI response sent via AppSync using senderId: '{ai_id}'")
        except Exception as e:
            print(f"AppSync error: {e}. Falling back to direct DynamoDB write.")
            ai_message = {
                'id': str(uuid.uuid4()),
                'chatroomId': chatroom_id,
                'text': ai_text,
                'senderId': ai_id,
                'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            }
            MESSAGES_TABLE.put_item(Item=ai_message)
            
    except Exception as e:
        print(f"Unexpected error in handler: {e}")
        raise