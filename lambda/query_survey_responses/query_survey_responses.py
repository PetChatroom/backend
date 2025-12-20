import boto3
import json
import os
from boto3.dynamodb.conditions import Key, Attr

# Initialize DynamoDB client
DYNAMODB = boto3.resource('dynamodb')
SURVEY_RESPONSES_TABLE_NAME = os.environ.get('SURVEY_RESPONSES_TABLE')

if not SURVEY_RESPONSES_TABLE_NAME:
    raise ValueError("SURVEY_RESPONSES_TABLE environment variable is not set")

SURVEY_RESPONSES_TABLE = DYNAMODB.Table(SURVEY_RESPONSES_TABLE_NAME)

def handler(event, context):
    """Query survey responses with optional filters."""
    try:
        # Extract filter parameters
        education_filter = event.get('education')
        llm_knowledge_filter = event.get('llmKnowledge')
        min_age = event.get('minAge')
        max_age = event.get('maxAge')
        chatbot_frequency_filter = event.get('chatbotFrequency')
        limit = event.get('limit', 100)
        
        # Start with scan (or use GSI if filtering by indexed fields)
        if education_filter:
            # Use education GSI
            response = SURVEY_RESPONSES_TABLE.query(
                IndexName='education-index',
                KeyConditionExpression=Key('education').eq(education_filter),
                Limit=limit
            )
        elif llm_knowledge_filter:
            # Use llmKnowledge GSI
            response = SURVEY_RESPONSES_TABLE.query(
                IndexName='llmKnowledge-index',
                KeyConditionExpression=Key('llmKnowledge').eq(llm_knowledge_filter),
                Limit=limit
            )
        else:
            # Full table scan
            response = SURVEY_RESPONSES_TABLE.scan(Limit=limit)
        
        items = response.get('Items', [])
        
        # Apply additional filters
        if min_age is not None:
            items = [item for item in items if item.get('age', 0) >= min_age]
        if max_age is not None:
            items = [item for item in items if item.get('age', 999) <= max_age]
        if chatbot_frequency_filter:
            items = [item for item in items if item.get('chatbotFrequency') == chatbot_frequency_filter]
        
        # Calculate statistics
        total_responses = len(items)
        correct_guesses = sum(1 for item in items if item.get('wasCorrect', False))
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'responses': items,
                'totalCount': total_responses,
                'correctGuesses': correct_guesses,
                'accuracy': (correct_guesses / total_responses * 100) if total_responses > 0 else 0
            }, default=str)
        }
        
    except Exception as e:
        print(f"Error querying survey responses: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
