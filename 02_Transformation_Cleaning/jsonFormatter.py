import json
import re
from urllib.parse import urlparse

def extract_metadata_and_webparts(file_path, add_prefix=False):
    with open(file_path, 'r') as file:
        data = json.load(file)

    # Extract metadata
    metadata = {
        'lastModifiedDateTime': data.get('lastModifiedDateTime'),
        'name': data.get('name'),
        'webUrl': data.get('webUrl'),
        'title': data.get('title')
    }

    # Extract the prefix from the webUrl
    web_url = metadata.get('webUrl', '')
    parsed_url = urlparse(web_url)
    prefix = f"{parsed_url.scheme}://{parsed_url.netloc}/"

    webparts = []

    def extract_content(obj):
        if isinstance(obj, dict):
            if 'columns' in obj:
                for column in obj['columns']:
                    column_info = {'width': column.get('width')}
                    webparts_list = []
                    for webpart in column.get('webparts', []):
                        webpart_info = {}
                        if 'serverProcessedContent' in webpart:
                            webpart_info['serverProcessedContent'] = webpart['serverProcessedContent']
                        if 'innerHtml' in webpart:
                            webpart_info['innerHtml'] = webpart['innerHtml']
                        if 'data' in webpart and 'title' in webpart['data']:
                            webpart_info['title'] = webpart['data']['title']
                        # Check for nested serverProcessedContent
                        nested_server_processed_content = extract_nested_server_processed_content(webpart)
                        if nested_server_processed_content:
                            webpart_info['nestedServerProcessedContent'] = nested_server_processed_content
                        webparts_list.append(webpart_info)
                    column_info['webparts'] = webparts_list
                    webparts.append(column_info)
            for key, value in obj.items():
                extract_content(value)
        elif isinstance(obj, list):
            for item in obj:
                extract_content(item)

    def extract_nested_server_processed_content(obj):
        if isinstance(obj, dict):
            if 'serverProcessedContent' in obj:
                return obj['serverProcessedContent']
            for key, value in obj.items():
                result = extract_nested_server_processed_content(value)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = extract_nested_server_processed_content(item)
                if result:
                    return result
        return None

    def add_prefix_to_relative_urls(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and re.match(r'.*\.(aspx|png|jpg|jpeg|gif|bmp|pdf|docx|xlsx|pptx)$', value) and not value.startswith(('http://', 'https://')):
                    obj[key] = prefix + value.lstrip('/')
                elif isinstance(value, (dict, list)):
                    add_prefix_to_relative_urls(value)
        elif isinstance(obj, list):
            for index, item in enumerate(obj):
                if isinstance(item, str) and re.match(r'.*\.(aspx|png|jpg|jpeg|gif|bmp|pdf|docx|xlsx|pptx)$', item) and not item.startswith(('http://', 'https://')):
                    obj[index] = prefix + item.lstrip('/')
                elif isinstance(item, (dict, list)):
                    add_prefix_to_relative_urls(item)

    extract_content(data)

    # Combine metadata and webparts into a single dictionary
    combined_data = {**metadata, 'webparts': webparts}

    # Optionally add prefix to relative URLs
    if add_prefix:
        add_prefix_to_relative_urls(combined_data)

    return combined_data

def save_to_json(data, output_file_path):
    with open(output_file_path, 'w') as file:
        json.dump(data, file, indent=2)

#GO to Graph Explorer - run following query:
#https://graph.microsoft.com/v1.0/sites/c4a7b3a3-0c67-498e-b974-fc9b5a62324d/pages/be29d9e0-e1ed-4e61-b889-67a6d2b7ada2/microsoft.graph.sitePage?$expand=canvasLayout

#copy and paste the output into a json file: graph_output_page1.json

# Usage
file_path = r"./01_SharePoint_Extractor/output/graph_output_myPage1.json"
extracted_content = extract_metadata_and_webparts(file_path, add_prefix=True)

# Print the extracted content
print(json.dumps(extracted_content, indent=2))

# Save the extracted content to a new JSON file
output_file_path = r"./02_Transformation_Cleaning/output/extracted_metadata_and_webparts1.json"
save_to_json(extracted_content, output_file_path)

#TODO
#impement function to download pictures and documents as it requires authentication through service principal to access the files through URL
#https://learn.microsoft.com/en-us/sharepoint/dev/spfx/use-aadhttpclient