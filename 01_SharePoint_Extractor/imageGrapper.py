import msal
import requests

#Since the REST-API is only serving the html content, we need to extract the image URL from the html content

# Define your parameters
Tenant= "<tenant>"
client_id = "<clientid>"
client_secret = "<clientsecret>" 
tenant_id = "<tenantid>"
authority = f'https://login.microsoftonline.com/{tenant_id}'
scope = ['https://{Tenant}.sharepoint.com/.default']
sharepoint_url = "https://{Tenant}.sharepoint.com/sites/YOUR_SITE/_api/web/getfilebyserverrelativeurl('/sites/YOUR_SITE/Shared%20Documents/YOUR_IMAGE.jpg')/$value"

# Create a confidential client application
app = msal.ConfidentialClientApplication(
    client_id,
    authority=authority,
    client_credential=client_secret
)

# Acquire a token
result = app.acquire_token_for_client(scopes=scope)

if 'access_token' in result:
    access_token = result['access_token']
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    # Make the request to download the image
    response = requests.get(sharepoint_url, headers=headers)

    if response.status_code == 200:
        with open('YOUR_IMAGE.jpg', 'wb') as file:
            file.write(response.content)
        print('Image downloaded successfully.')
    else:
        print(f'Failed to download image. Status code: {response.status_code}')
else:
    print('Failed to acquire token.')
