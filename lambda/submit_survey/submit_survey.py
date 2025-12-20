import boto3
import json
import os
import uuid
from datetime import datetime, timezone

# Initialize DynamoDB client
DYNAMODB = boto3.resource('dynamodb')
SURVEY_RESPONSES_TABLE_NAME = os.environ.get('SURVEY_RESPONSES_TABLE')

if not SURVEY_RESPONSES_TABLE_NAME:
    raise ValueError("SURVEY_RESPONSES_TABLE environment variable is not set")

SURVEY_RESPONSES_TABLE = DYNAMODB.Table(SURVEY_RESPONSES_TABLE_NAME)

def handler(event, context):
    """Saves survey response to DynamoDB."""
    try:
        # Extract survey data from event
        chatroom_id = event.get('chatroomId')
        user_id = event.get('userId')
        bot_guess = event.get('botGuess')  # Player 1 or Player 2
        reasoning = event.get('reasoning', '')
        llm_knowledge = event.get('llmKnowledge')  # None, Some, High, Expert
        chatbot_frequency = event.get('chatbotFrequency')  # Never, Daily, Weekly, Monthly
        age = event.get('age')
        education = event.get('education')  # None, Highschool, Undergraduate, Postgraduate
        
        # Validate required fields
        if not all([chatroom_id, user_id, bot_guess, llm_knowledge, chatbot_frequency, age, education]):
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required fields'})
            }
        
        # Create survey response item
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        survey_response = {
            'id': str(uuid.uuid4()),
            'timestamp': timestamp,
            'chatroomId': chatroom_id,
            'userId': user_id,
            'botGuess': bot_guess,
            'reasoning': reasoning,
            'llmKnowledge': llm_knowledge,
            'chatbotFrequency': chatbot_frequency,
            'age': int(age),
            'education': education,
        }
        
        # Save to DynamoDB
        SURVEY_RESPONSES_TABLE.put_item(Item=survey_response)
        
        print(f"Survey response saved: {survey_response['id']}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'id': survey_response['id'],
                'timestamp': timestamp
            })
        }
        
    except Exception as e:
        print(f"Error saving survey response: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
