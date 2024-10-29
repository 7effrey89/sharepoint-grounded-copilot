import json
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import os
import pandas as pd
from datetime import datetime
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

AZURE_SQL_server = "<sql-server>.database.windows.net"
AZURE_SQL_database = "<database>"
AZURE_SQL_username = "<username>"
AZURE_SQL_password = "<password1>"
AZURE_SQL_driver = "ODBC Driver 17 for SQL Server"

# Load environment variables from .env file
load_dotenv()

# Connection string
SERVER = os.getenv("AZURE_SQL_server") 
DATABASE = os.getenv("AZURE_SQL_database")
USERNAME = os.getenv("AZURE_SQL_username")
PASSWORD = os.getenv("AZURE_SQL_password")
DRIVER = os.getenv("AZURE_SQL_driver")


# Azure Cognitive Search configuration
SEARCH_SERVICE_ENDPOINT = os.environ["AZURE_SEARCH_SERVICE_ENDPOINT"]
SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX", "int-vec")
credential = AzureKeyCredential(os.getenv("AZURE_SEARCH_ADMIN_KEY")) if os.getenv("AZURE_SEARCH_ADMIN_KEY") else DefaultAzureCredential()



# Database and table details
TABLE_SCHEMA = 'dbo'
TABLE_NAME = 'sharepoint_pages'
QUERY = f'SELECT id, page_id, lastModifiedDateTime, name, webUrl, title, is_active, lastExtractionDateTime FROM {TABLE_SCHEMA}.{TABLE_NAME};'
DROP_TABLE = f"DROP TABLE {TABLE_SCHEMA}.{TABLE_NAME}"
INIT_TABLE = f"""
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '{TABLE_NAME}' AND schema_id = SCHEMA_ID('{TABLE_SCHEMA}'))
CREATE TABLE {TABLE_SCHEMA}.{TABLE_NAME} (
    id INT IDENTITY(1,1),
    page_id VARCHAR(100), 
    site_id VARCHAR(100), 
    lastModifiedDateTime datetime,
    name VARCHAR(100),
    webUrl VARCHAR(100),
    title VARCHAR(100),
    is_active bit,
    lastExtractionDateTime datetime,
);
"""

def getCurrentDateTime():
    current_datetime = datetime.now()

    # Format the datetime as yyyy-mm-dd hh:mm:ss
    return current_datetime.strftime('%Y-%m-%d %H:%M:%S')

def init_connection():
    """
    Initializes a connection to the database using the provided credentials.

    Returns:
        engine (sqlalchemy.engine.Engine): The SQLAlchemy engine object representing the database connection.
    """
    # Create connection engine
    connection_string = f'mssql+pyodbc://{USERNAME}:{PASSWORD}@{SERVER}/{DATABASE}?driver={DRIVER}'
    engine = create_engine(connection_string, echo=True)
    return engine

def execute_sql_command(batch_command):
    """
    Executes a batch SQL command.
    """
    engine = init_connection()
    with engine.begin() as conn:
        conn.execute(text(batch_command))

# CRUD operations
def Select_query(query):
    engine = init_connection()
    with engine.connect() as connection:
        result = pd.read_sql_query(query, connection.connection)
        return result
    
def update_sharepoint_watermark_table(added_rows, siteID):
    if not added_rows:
        return
    
    # Create a single SELECT statement with UNION ALL
    select_statements = []
    for row in added_rows:
        select_statement = f"""
        SELECT '{row['id']}' AS page_id, 
               '{siteID}' AS site_id, 
               '{row['lastModifiedDateTime']}' AS lastModifiedDateTime, 
               '{row['name']}' AS name, 
               '{row['webUrl']}' AS webUrl, 
               '{row['title']}' AS title
        """
        select_statements.append(select_statement)
    
    # Combine all SELECT statements with UNION ALL
    combined_select = " UNION ALL ".join(select_statements)
    
    # Create the MERGE command using the combined SELECT statement
    merge_command = f"""
    MERGE INTO {TABLE_SCHEMA}.{TABLE_NAME} AS target
    USING ({combined_select}) AS source
    ON (target.page_id = source.page_id)
    WHEN MATCHED THEN
        UPDATE SET 
            target.lastModifiedDateTime = source.lastModifiedDateTime,
            target.name = source.name,
            target.webUrl = source.webUrl,
            target.title = source.title,
            target.is_active = 1
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (page_id, site_id, lastModifiedDateTime, name, webUrl, title, is_active, lastExtractionDateTime)
        VALUES (source.page_id, source.site_id, source.lastModifiedDateTime, source.name, source.webUrl, source.title, 1, 0)
    WHEN NOT MATCHED BY SOURCE THEN
       UPDATE SET target.is_active = 0
    ;
    """
    execute_sql_command(merge_command)

def update_page_watermark(page_id, currentDateTime):

    batch_command = f"UPDATE {TABLE_SCHEMA}.{TABLE_NAME} SET lastExtractionDateTime='{currentDateTime}' WHERE page_id = '{page_id}'"

    print(batch_command)
    execute_sql_command(batch_command)

#Initiate the watermark
execute_sql_command(INIT_TABLE)

def get_Site(sharepointTitle):
    #issue a graph query to get the siteID based on the sharepointTitle

    # if sharepointTitle == "GettingReadyforTridentFabric":
    #     return "c4a7b3a3-0c67-498e-b974-fc9b5a62324d"

    #example of query:
    #https://graph.microsoft.com/v1.0/sites/microsofteur.sharepoint.com:/teams/GettingReadyforTridentFabric  
    url = f"https://graph.microsoft.com/v1.0/sites/microsofteur.sharepoint.com:/teams/{sharepointTitle}"

    #sample of the query output:
    file_path = r"./01_SharePoint_Extractor/output/graph_output_site.json" #replace with output of rest call

    with open(file_path, 'r') as file:
        # Read the file content
        file_content = file.read()
        # Parse the JSON data
        data = json.loads(file_content)

        # Extract the id field
        id_field = data['id']

        # Split the id field by commas and get the second part
        site_id = id_field.split(',')[1]

        return site_id

def get_SitePages(siteID):
    #issue a graph query to get the pages based on the sharepoint id
    
    #example of query:
    #https://graph.microsoft.com/v1.0/sites/microsofteur.sharepoint.com:/teams/GettingReadyforTridentFabric  
    url = f"https://graph.microsoft.com/v1.0/sites/{siteID}/pages?select=id,name,title,weburl,lastModifiedDateTime"
    
    #sample of the query output:
    file_path = r"./01_SharePoint_Extractor/output/graph_output_site_pages.json" #replace with output of rest call

    with open(file_path, 'r') as file:
        # Read the file content
        file_content = file.read()
        # Parse the JSON data
        data = json.loads(file_content)

        return data

def page_extractor(siteID, page_id):
    #Connect to Graph

    #Issue graph Query: 
    url = f"https://graph.microsoft.com/v1.0/sites/{siteID}/pages/{page_id}/microsoft.graph.sitePage?$expand=canvasLayout"
    
    #Samples graph Query: 
    # MyPage1.aspx:
    # https://graph.microsoft.com/v1.0/sites/c4a7b3a3-0c67-498e-b974-fc9b5a62324d/pages/be29d9e0-e1ed-4e61-b889-67a6d2b7ada2/microsoft.graph.sitePage?$expand=canvasLayout

    # MyPage2.aspx:
    # https://graph.microsoft.com/v1.0/sites/c4a7b3a3-0c67-498e-b974-fc9b5a62324d/pages/41c59019-d5ad-41f7-8ddb-b7804e540b54/microsoft.graph.sitePage?$expand=canvasLayout
    
    #dump the response to a json file
    #output './01_SharePoint_Extractor/output/graph_output_myPage1.json 
    #output './01_SharePoint_Extractor/output/graph_output_myPage2.json

def updated_documents(sharepointTitle, currentDateTime):
    #Issue graph Query: Get SiteID based on sharepointTitle
    siteID = get_Site(sharepointTitle)

    jsonData = get_SitePages(siteID)

    #insert and update watermark table
    update_sharepoint_watermark_table(jsonData['value'], siteID)

    # Show the watermark table
    df = Select_query(QUERY)
    # print(df)
    
    # Initialize an empty list to store updated rows
    updated_pages_documents = []

    # Compare 'lastModifiedDateTime' with 'lastExtractionDateTime' and extract the page if it is newer
    for index, row in df.iterrows():
        if pd.to_datetime(row['lastModifiedDateTime']) > pd.to_datetime(row['lastExtractionDateTime']):
            page_extractor(siteID, row['page_id']) #extract html from sharepoint page 
            update_page_watermark(row['page_id'], currentDateTime) #update the lastExtractionDateTime in watermark table

            updated_pages_documents.append(row['page_id'] + '.json')  # Append the updated page_id to the list

    return updated_pages_documents



#Remove existing documents in search index to avoid left-overs if previous document was longer than the current one
def removeDocumentInAISearchIndex(array_document_name_and_extention):
    #figure out how to retrieve all chucnk_ids for the same docuent, they share same parentid or title page_id+.json
    # Create a SearchClient
    search_client = SearchClient(endpoint=SEARCH_SERVICE_ENDPOINT,
                                index_name=SEARCH_INDEX_NAME,
                                credential=credential)
        
    for document_name_and_extension in array_document_name_and_extention:
        # Search for documents where title matches the current document name and extension. we assume top 1000 results will cover all chunks related to the document.
        search_results = search_client.search(search_text="*", filter=f"title eq '{document_name_and_extension}'", top=1000)

        # Extract chunk_id values
        chunk_ids = [doc['chunk_id'] for doc in search_results if 'chunk_id' in doc]

        print(f"Chunk IDs for {document_name_and_extension}:", chunk_ids)

        # Loop through chunk_ids and delete each document
        for chunk_id in chunk_ids:
            document_key = chunk_id
            result = search_client.delete_documents(documents=[{"chunk_id": document_key}])
            print(f"Deletion of document {document_key} succeeded: {result[0].succeeded}")


###############################################

currentDateTime = getCurrentDateTime()

updated_documents = updated_documents("GettingReadyforTridentFabric", currentDateTime)

#Remove existing documents in search index to avoid left-overs if previous document was longer than the current one
removeDocumentInAISearchIndex(updated_documents)

#Run azure-search-integrated-vectorization-sample.ipynb to start uploading .json files from 03_AISearch_Ingestion/data/documents/ to Azure Blob Storage
    #optional: empty the folder 03_AISearch_Ingestion/data/documents/ before running the notebook to avoid uploading unchanged files OR
    #or moves files around in folder to keep status of new and old files