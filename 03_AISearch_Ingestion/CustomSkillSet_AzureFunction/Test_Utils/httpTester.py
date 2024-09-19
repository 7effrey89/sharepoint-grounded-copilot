import json
import requests

# Load the JSON content from the file
with open('./03_AISearch_Ingestion/CustomSkillSet_AzureFunction/Test_Utils/extracted_metadata_and_webparts.json', 'r', encoding='utf-8') as file:
    json_content = json.load(file)

# URL of the Azure Function - default (Function key)
# Master Key (Host Key):

# This key provides full access to all functions within the function app.
# It is the most powerful key and should be used sparingly.
# Typically used for administrative tasks.
# Function Key:

# This key provides access to a specific function.
# Each function can have its own function key.
# It is more secure than using the master key because it limits access to a single function.
# Host Key:

# This key provides access to all functions within the function app, similar to the master key but with slightly less privilege.
# It is used to access all functions within the app without needing the master key.
url = "https://jlacustomskillmetadataextractor.azurewebsites.net/api/MyCustomSkillApp?code=bgCaDyNQw5NtOitjPrdA7sA4uZlcS2n5m4CIEt2U0GmfAzFuiiQdWw%3D%3D"

# Headers to specify the content type
headers = {"Content-Type": "application/json"}

# # JSON payload
# data = {
#     "innerHTML": "<p><strong>Arbejdssteder</strong></p><p>Jyske Bank</p><p><strong>Roller</strong></p><p>Alle medarbejdere</p>"
# }

# The name of the json property that will contain the content that needs to be sent to the azure function
inputField = "text"

# Prepare the values array with recordId and data properties
values = [
    {
        "recordId": "0",
        "data": {
            inputField: json_content
        }
    }
]

# JSON payload
data = {
    "values": values
}

# Send the POST request with the JSON payload
response = requests.post(url, headers=headers, json=data)

# Print the raw response content
print(response.content)

# Try to parse the response as JSON and print it
try:
    print(response.json())
except requests.exceptions.JSONDecodeError:
    print("Response is not in JSON format")