import json
import requests  # Example of an external dependency

def handler(event, context):
    """
    This function gets the current time from an external API.
    """
    try:
        response = requests.get("http://worldtimeapi.org/api/ip")
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        current_time = data.get("datetime")

        return {
            "statusCode": 200,
            "body": json.dumps({"currentTime": current_time})
        }
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to retrieve time"})
        }