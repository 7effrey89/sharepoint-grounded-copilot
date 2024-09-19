import os
import json
import requests
from bs4 import BeautifulSoup
from azure.identity import DefaultAzureCredential, get_bearer_token_provider, EnvironmentCredential
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from datetime import datetime

AZURE_OPENAI_API_KEY=os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT=os.environ["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_TEXT_DEPLOYMENT_NAME=os.getenv("AZURE_OPENAI_TEXT_DEPLOYMENT_NAME")
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION="2024-05-01-preview"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002") 


# Azure Cognitive Search configuration
SEARCH_SERVICE_ENDPOINT = os.environ["AZURE_SEARCH_SERVICE_ENDPOINT"]
SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX", "int-vec")
credential = AzureKeyCredential(os.getenv("AZURE_SEARCH_ADMIN_KEY")) if os.getenv("AZURE_SEARCH_ADMIN_KEY") else DefaultAzureCredential()

AZURE_CLIENT_ID="090b4185-139c-47ed-941c-170cf87ade9a"
AZURE_TENANT_ID="16b3c013-d300-468d-ac64-7eda0820b6d3"
AZURE_CLIENT_SECRET_ID="7ab116d1-eb07-422d-a89a-76a9494e5a4f" #SecretID
AZURE_CLIENT_SECRET="a-p8Q~NNs_rKlpCUad1JSJk5S.xC-qduW9mEtboJ" #Value

os.environ["AZURE_CLIENT_ID"] = AZURE_CLIENT_ID
os.environ["AZURE_CLIENT_SECRET"] = AZURE_CLIENT_SECRET
os.environ["AZURE_TENANT_ID"] = AZURE_TENANT_ID



# Create a SearchClient
search_client = SearchClient(endpoint=SEARCH_SERVICE_ENDPOINT,
                             index_name=SEARCH_INDEX_NAME,
                             credential=credential)

def get_current_datetime():
    now = datetime.now()
    return now.strftime("%d-%m-%Y %H:%M:%S")

def search_index(query, filter_expression=None):
    # Perform the search
    results = search_client.search(
            search_text=query, 
            query_type="semantic", #will perform hybrid search by default using this
            semantic_configuration_name='my-semantic-config', #set during the index creation. Enables semantic reranking
            select='title, chunk, arbejdssteder, roller, page_number',
            filter=filter_expression,  # Apply the filter expression if provided
            top=10
        )
    
    # Return the results as a list
    return [result for result in results]

#Custom functions that can be called by the LLM. Providing insights into the arguments that are required for the function to be called.
custom_functions = [
    {
        "name": "search_index",
        "description": "Search the VIS index",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "filter": {
                    "type": "string",
                    "description": "The filter expression (e.g., \"category eq 'electronics'\")"
                }
            },
            "required": ["query"]
        }
    }, 
    {
        "name": "getTime",
        "description": "return the current date and time",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "return the current date and time"
                }
            }
        }
    }, 
]

def generate_response(chat_history1, user_input):
    chat_history1.append({"role": "user", "content": user_input})

    #provide response from the LLM. If it wants to call a function, it will instead provide the function name and arguments to be passed to the function
    response = Call_LLM_Agent(chat_history1,AZURE_OPENAI_CHAT_DEPLOYMENT_NAME)

    #provides the same response from previous step, but if previous step was a function call, it will invoke the function and provide a synthesized reponse made of the result of the function call and chat history
    ToolResponse = LLM_ToolInvoker(response, chat_history1)

    chat_history1.append({"role": "assistant", "content": ToolResponse})
    return ToolResponse

#Configuration of the LLM
def Call_LLM_Agent(chat_history, model=AZURE_OPENAI_TEXT_DEPLOYMENT_NAME):
    #giving the choice to specify which llm model to provide the response. GPT-4o mini for simple task such as generating queries, and GPT-4o for more complex tasks such as providing good answers.
    credential = DefaultAzureCredential() #EnvironmentCredential() 
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

    client = AzureOpenAI(azure_endpoint=AZURE_OPENAI_ENDPOINT, 
                        azure_ad_token_provider=token_provider, 
                        # api_key=AZURE_OPENAI_API_KEY,
                        api_version=AZURE_OPENAI_API_VERSION)
    
    #return a response from the LLM or which function and params to to invoke   
    return client.chat.completions.create(
        model=model, # deployment_id could be one of {gpt-35-turbo, gpt-35-turbo-16k}
        messages=chat_history,
        functions = custom_functions,
        function_call = 'auto',
        temperature=0)


#Instructions to the LLM for how to execute a "Tool", and log the actions and results between the llm and tool interaction to provide the LLM context of what has happend so far
def LLM_ToolInvoker(response, chat_history):
    #Getting assistant message 
    response_message = response.choices[0].message

    # Call python function
    if dict(response_message).get('function_call'):
            
        # Which function call was invoked
        function_called = response_message.function_call.name
        
        # Extracting the arguments
        function_args  = json.loads(response_message.function_call.arguments)
        
        # Function names
        available_functions = {
            "search_index": search_index,
            "getTime" : get_current_datetime
        }
        
        #determine which function to call
        fuction_to_call = available_functions[function_called]

        # append assistant's to history that we call the function and the passed arguments
        chat_history.append({"role": "assistant", "content": "null", "function_call": {"name": "" + function_called + "", "arguments": "" + json.dumps(function_args)}})

        # execute the function, and get return value from function
        custom_function_response = fuction_to_call(*list(function_args .values()))

        # append assistant's to history the result/response from the custom function
        chat_history.append({"role": "function", "name": function_called, "content": json.dumps(custom_function_response)})
        
        #after function has finished, and delivered result back to the chat history, assistant looks at chat history and provides a response to the user.
        final_message = Call_LLM_Agent(chat_history, AZURE_OPENAI_TEXT_DEPLOYMENT_NAME)
        final_message = final_message.choices[0].message.content
    else:
        #if not using function calling, return the llm response to user
        final_message = response_message.content
        
    return(final_message)

# Interactive loop
def interactive_loop(chat_history):

    print("Interactive Azure OpenAI Chat. Type 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break
        if user_input.lower() == "history":
            for item in chat_history:
                print(item)
                print() 
        if user_input.lower() != "history":
        
            response = generate_response(chat_history, user_input)

            print(f"Assistant: {response}")



###################################

# Start the interactive loop
#Start demo1: What does tft stands for
#Start demo2: What does tft stands for. Only find results where arbejdssteder=Jyske Bank' - consider making prompt templates

my_chat_history=[
        {"role": "system", "content": "You are a helpful assistant. You will always search within the VIS index before providing an answer. "},
        {"role": "user", "content": "My name is Jeffrey Lai, what time is it?"},
        {"role": "assistant", "content": "Hi Jeffrey, the time is " + get_current_datetime() + ". How can I help you today?"},
    ]
interactive_loop(my_chat_history)