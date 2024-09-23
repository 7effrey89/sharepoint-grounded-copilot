import os
import json

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from datetime import datetime
import requests
import streamlit as st

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

AZURE_CLIENT_ID=os.getenv("AZURE_CLIENT_ID")
AZURE_TENANT_ID=os.getenv("AZURE_TENANT_ID")
AZURE_CLIENT_SECRET=os.getenv("AZURE_CLIENT_SECRET")

os.environ["AZURE_CLIENT_ID"] = AZURE_CLIENT_ID
os.environ["AZURE_CLIENT_SECRET"] = AZURE_CLIENT_SECRET
os.environ["AZURE_TENANT_ID"] = AZURE_TENANT_ID

# isStreaming = True #doesn't need to restart the program to work :)
useIdentity = False

# Create a SearchClient
search_client = SearchClient(endpoint=SEARCH_SERVICE_ENDPOINT,
                             index_name=SEARCH_INDEX_NAME,
                             credential=credential)

################### TOOLS ########################
def tool_get_coordinates(city_name):
    # Construct the API endpoint
    url = f"https://nominatim.openstreetmap.org/search?q={city_name}&format=json&limit=1"

    # Make the GET request
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        if data:
            latitude = data[0].get('lat')
            longitude = data[0].get('lon')
            return latitude, longitude
        else:
            print("Coordinates not found.")
            return None, None
    else:
        print("Error fetching coordinates.")
        return None, None

def tool_current_weather(latitude, longitude):

    # Replace with the latitude and longitude of your location
    # latitude = "55.6761"  # Example: Copenhagen
    # longitude = "12.5683" #

    # Construct the API endpoint
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"

    # Make the GET request
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        current_weather = data.get('current_weather')
        if current_weather:
            temperature = current_weather.get('temperature')
            wind_speed = current_weather.get('windspeed')
            time = current_weather.get('time', datetime.utcnow().isoformat())
    #         print(f"Current weather at {latitude}, {longitude} (Copenhagen):")
    #         print(f"Temperature: {temperature}°C")
    #         print(f"Wind Speed: {wind_speed} km/h")
    #         print(f"Time: {time}")
    #     else:
    #         print("Current weather data not found.")
    # else:
    #     print("Failed to retrieve data.")
    
    return data

def tool_current_datetime():
    now = datetime.now()
    return now.strftime("%d-%m-%Y %H:%M:%S")

def tool_ai_search_index(query, filter_expression=None):

    if "JyskeBank" and "Microsoft" in st.session_state:
        if st.session_state["JyskeBank"] and st.session_state["Microsoft"]:
            filter_expression = "arbejdssteder eq 'Jyske Bank' or arbejdssteder eq 'Microsoft'"
        elif st.session_state["JyskeBank"]:
            filter_expression = "arbejdssteder eq 'Jyske Bank'"
        elif st.session_state["Microsoft"]:
            filter_expression = "arbejdssteder eq 'Microsoft'"

    # Perform the search
    results = search_client.search(
            search_text=query, 
            query_type="semantic", #will perform hybrid search by default using this
            semantic_configuration_name='my-semantic-config', #set during the index creation. Enables semantic reranking
            select='title, chunk, arbejdssteder, roller',
            filter=filter_expression,  # Apply the filter expression if provided
            top=10
        )
    
    # Return the results as a list
    return [result for result in results]

###################################################

def generate_response(chat_history, user_input):
    chat_history.append({"role": "user", "content": user_input})

    FinishedProcessing = False
    
    while not FinishedProcessing:
        #provide response from the LLM. If it wants to call a function, it will instead provide the function name and arguments to be passed to the function
        response = Call_LLM_Agent(chat_history,AZURE_OPENAI_CHAT_DEPLOYMENT_NAME)

        #provides the same response from previous step, but if previous step was a function call, it will invoke the function and provide a synthesized reponse made of the result of the function call and chat history
        toolInvoked = LLM_ToolInvoker(response, chat_history)

        if toolInvoked:
            FinishedProcessing = False
        else:
            FinishedProcessing = True

    FinalResponse = response.choices[0].message.content
    # #provide response from the LLM. If it wants to call a function, it will instead provide the function name and arguments to be passed to the function
    # response = Call_LLM_Agent(chat_history,AZURE_OPENAI_CHAT_DEPLOYMENT_NAME)

    # #provides the same response from previous step, but if previous step was a function call, it will invoke the function and provide a synthesized reponse made of the result of the function call and chat history
    # toolInvoked = LLM_ToolInvoker(intermediaResponse, chat_history)


    chat_history.append({"role": "assistant", "content": FinalResponse})


    with st.chat_message("Assistant"): #with st.chat_message("assistant", avatar="./Snowflake_Logomark_blue.svg"):
        st.write(FinalResponse)

    return FinalResponse

#Configuration of the LLM
def Call_LLM_Agent(chat_history, model=AZURE_OPENAI_TEXT_DEPLOYMENT_NAME):
    #giving the choice to specify which llm model to provide the response. GPT-4o mini for simple task such as generating queries, and GPT-4o for more complex tasks such as providing good answers.
    credential = DefaultAzureCredential() #EnvironmentCredential() 
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

    if useIdentity:
        client = AzureOpenAI(azure_endpoint=AZURE_OPENAI_ENDPOINT, 
                            azure_ad_token_provider=token_provider, 
                            # api_key=AZURE_OPENAI_API_KEY,
                            api_version=AZURE_OPENAI_API_VERSION)
    else:
        client = AzureOpenAI(azure_endpoint=AZURE_OPENAI_ENDPOINT, 
                    api_key=AZURE_OPENAI_API_KEY,
                    api_version=AZURE_OPENAI_API_VERSION)
        
    
    #Custom functions that can be called by the LLM. Providing insights into the arguments that are required for the function to be called.
    custom_functions = []

    # Check each tool_getX key and add functions conditionally
    if st.session_state.get("tool_getRAG", False):
        custom_functions.append({
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
                        "description": "The filter expression (e.g., \"category eq 'electronics'\"). \
                            The search index field is always with lowercase. \
                            Always use a specified filter expression from the user request. \
                            The index is populated with the following fields: informationstype, overordnet_emne: ['It', 'HR'], emne: ['Teams for Tribes', 'Health and Wellness'], arbejdssteder: ['Microsoft', 'Jyske Bank'], roller: ['Alle medarbejdere', 'SME']."
                    }
                },
                "required": ["query"]
            }
        })

    if st.session_state.get("tool_getTime", False):
        custom_functions.append({
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
        })

    if st.session_state.get("tool_getWeather", False):
        custom_functions.append({
            "name": "getWeather",
            "description": "Get the current weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "string",
                        "description": "The latitude of the location"
                    },
                    "longitude": {
                        "type": "string",
                        "description": "The longitude of the location"
                    }
                },
                "required": ["latitude", "longitude"]
            }
        })

    if st.session_state.get("tool_getCoordinates", False):
        custom_functions.append({
            "name": "getCoordinates",
            "description": "Get the coordinates of a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The name of the location"
                    }
                },
                "required": ["location"]
            }
        })

    
    #return a response from the LLM or which function and params to to invoke   
    return client.chat.completions.create(
        model=model, # deployment_id could be one of {gpt-35-turbo, gpt-35-turbo-16k}
        messages=chat_history,
        functions = custom_functions,
        function_call = 'auto', #tool_choice: {"type": "function", "function": {"name": "my_function"}}.
        temperature=0)


#Instructions to the LLM for how to execute a "Tool", and log the actions and results between the llm and tool interaction to provide the LLM context of what has happend so far
def LLM_ToolInvoker(response, chat_history):
    #Getting assistant message 
    response_message = response.choices[0].message
    
    toolInvoked = False
    # Call python function
    if dict(response_message).get('function_call'):
            
        # Which function call was invoked
        function_called = response_message.function_call.name
        
        # Extracting the arguments
        function_args  = json.loads(response_message.function_call.arguments)
        
        # Function names - enable all by default
        # available_functions = {
        #     "search_index": tool_ai_search_index,
        #     "getTime" : tool_current_datetime,
        #     "getWeather": tool_current_weather,
        #     "getCoordinates": get_coordinates,
        # }

        # Initialize an empty dictionary
        available_functions = {}

        # Check each tool_getX key and add functions conditionally
        if st.session_state.get("tool_getRAG", False):
            available_functions["search_index"] = tool_ai_search_index

        if st.session_state.get("tool_getTime", False):
            available_functions["getTime"] = tool_current_datetime

        if st.session_state.get("tool_getWeather", False):
            available_functions["getWeather"] = tool_current_weather

        if st.session_state.get("tool_getCoordinates", False):
            available_functions["getCoordinates"] = tool_get_coordinates


        #determine which function to call
        fuction_to_call = available_functions[function_called]

        # append assistant's to history that we call the function and the passed arguments
        chat_history.append({"role": "assistant", "content": "null", "function_call": {"name": "" + function_called + "", "arguments": "" + json.dumps(function_args)}})

        with st.chat_message("Assistant"):
            st.write(f"function_call: {function_called}, arguments: {json.dumps(function_args)}") #will contain the function call and arguments
    
        # execute the function, and get return value from function
        custom_function_response = fuction_to_call(*list(function_args .values()))

        # append assistant's to history the result/response from the custom function
        chat_history.append({"role": "function", "name": function_called, "content": json.dumps(custom_function_response)})

        with st.chat_message("🔧"):
            st.write(f"Function: {function_called}")
            with st.container(height=300):
                st.write(f"{json.dumps(custom_function_response)}")
        
        toolInvoked = True

    return toolInvoked

def show_chat_history():
    messages = st.session_state["chat_history"]

    for i in range(len(messages)):
        msg = messages[i]
        if msg['role'] == "user":
            with st.chat_message("Human"):
                st.write(msg['content'])

        if msg['role'] == "assistant":
            with st.chat_message("Assistant"):
                if msg['content'] == "null":
                    st.write(f"function_call: {msg['function_call']['name']}, arguments: {msg['function_call']['arguments']}") #will contain the function call and arguments
                else:
                    st.write(msg['content'])

        if msg['role'] == "function":
            with st.chat_message("🔧"):
                st.write(f"Function: {msg['name']}")
                with st.container(height=300):
                    st.write(f"{msg['content']}")

##################################
#Best practice for prompt engineering
#https://help.openai.com/en/articles/6654000-best-practices-for-prompt-engineering-with-the-openai-api#h_21d4f4dc3d



######################################
sysMsg="You are a helpful assistant. You will always search within the VIS index before providing an answer."

def getPromptTemplate(subject, user_prompt):
    return f"Use search_index and parameter property: \
            filter: 'emne eq '{subject}'' \
            ### input: {user_prompt} ###"

                   
def getDefaultAssistant():
    #will overwrite the chat history
    my_chat_history=[
        {"role": "system", "content": sysMsg},
        {"role": "user", "content": "My name is Jeffrey Lai, what time is it?"},
        {"role": "assistant", "content": "Hi Jeffrey, the time is " + tool_current_datetime() + ". How can I help you today?"},
    ]
    st.session_state["chat_history"] = my_chat_history 
    st.session_state["CurrentSystemMsg"] = sysMsg #save the current system message
    st.session_state["promptTemplate"] = None

def getSMEAssistant(subjectArea):
    #will overwrite the chat history
    if subjectArea == "Teams for Tribes":
        domainSpecific = f"emne eq '{subjectArea}' and arbejdssteder eq 'Jyske Bank' for Teams TfT-enrollment for a tribe in Jyske bank"
    else:
        domainSpecific = f"emne eq '{subjectArea}' and arbejdssteder eq 'Microsoft' for HR Handbook for Microsoft Contoso"

    sysMsg=f"You will provide concise summary regarding ***{subjectArea}***. \
            You will always search within the VIS index before providing an answer. \
            Always use the search filter expression: ***{domainSpecific}*** related questions\
            Answer in bullet points. \
            If you are unsure and dont have enough facts and context to narrow down your search in VIS, ask for clarification. "
    
    
    my_chat_history=[
        {"role": "system", "content":sysMsg.replace("***","")}, #remove the markdown formatting again for the system message 
    ]
    st.session_state["chat_history"] = my_chat_history
    st.session_state["CurrentSystemMsg"] = sysMsg #save the current system message
    # st.session_state["promptTemplate"] = getPromptTemplate(subjectArea, "Your input here") #you can enable this to force using a prompt template
    


def AssistantStateControl():
    # Check if the state has changed
    if st.session_state["SubjectSearch"] != st.session_state["previous_subject_search"]:
        # Trigger the appropriate function based on the new state
        if st.session_state["SubjectSearch"] == "None":
            getDefaultAssistant()
        else:
            getSMEAssistant(st.session_state["SubjectSearch"])

        # Update the previous state to the current state
        st.session_state["previous_subject_search"] = st.session_state["SubjectSearch"]

def iniSessionStates():
    if "previous_subject_search" not in st.session_state:
        st.session_state["previous_subject_search"] = ""

    if "SubjectSearch" not in st.session_state:
        st.session_state["SubjectSearch"] = "None" 

    if "promptTemplate" not in st.session_state:
        st.session_state["promptTemplate"] = None

    if "chat_history" not in st.session_state:
        getDefaultAssistant()

    if "tool_getRAG" not in st.session_state:
        st.session_state["tool_getRAG"] = True

    if "tool_getGps" not in st.session_state:
        st.session_state["tool_getGps"] = True 

    if "tool_getWeather" not in st.session_state:
        st.session_state["tool_getWeather"] = True

    if "tool_getTime" not in st.session_state:
        st.session_state["tool_getTime"] = False
            
    if "CurrentSystemMsg" not in st.session_state:
        st.session_state["CurrentSystemMsg"] = ""
###################################

# Start the interactive loop
#Start demo1: What does tft stands for
#Start demo2: What does tft stands for. Only find results where arbejdssteder='Jyske Bank' - consider making prompt templates
#start demo3: Find hr stuff. Only find results where arbejdssteder=Jyske Bank' #shows filter working, as HR stuff only in arbejdssteder='Microsoft'

iniSessionStates()
show_chat_history()

# Get user input
user_prompt = st.chat_input("Enter your message here")

if user_prompt is not None and user_prompt != "":

    with st.chat_message("Human"):
        #use prompt template if enabled
        if st.session_state["promptTemplate"] is not None:
            user_prompt= st.session_state["promptTemplate"].replace("USER-PROMPT", user_prompt)

        st.write(f"{user_prompt}")

    generate_response(st.session_state["chat_history"], user_prompt)
    
with st.sidebar:
    st.title("Search Scope")

    st.write("Arbejdspladser")
    st.caption("Search Engine based filter level")
    st.session_state["JyskeBank"] = st.toggle("Jyske Bank Only")
    st.session_state["Microsoft"] = st.toggle("Microsoft Only")
    st.info('Hard filter - cannot be bypassed by AI', icon="ℹ️")

    st.divider()
    
    st.write("Subject Area")
    st.session_state['SubjectSearch'] = st.radio("Instruction based filter level - not hard filter",options=["Teams for Tribes", "Health and Wellness", "None"],index=2, captions=["Teams knowlege", "HR knowledge", "All knowledge"])
    AssistantStateControl()

    sysMessageView = st.toggle("Show system message")

    if sysMessageView:
        st.markdown(st.session_state["CurrentSystemMsg"])


    togglePromptTemplate = st.toggle("Use prompt template")

    if togglePromptTemplate:
        st.session_state['promptTemplate'] = st.radio("Prompt Templates",
                                                options=[
                                                "Always use search_index and filter expression: 'overordnet_emne eq 'It''. \
                                                It stands for Information Technology. Find related best practices around Microsoft M365 implementation incl Microsoft Teams and Microsoft CoPilot.\
                                                Provide summary of the content in 2 sentences . \
                                                ### input: USER-PROMPT ###",
                                                "Take a step-by-step approach in your response, cite sources and give reasoning before sharing final answer.\
                                                ### input: USER-PROMPT ###", 
                                                None],
                                                index=2)

    st.title("Tools")
    st.session_state["tool_getRAG"] = st.toggle("getVIS", value=True)
    st.session_state["tool_getGps"] = st.toggle("getGps", value=True)
    st.session_state["tool_getWeather"] = st.toggle("getWeather", value=True)
    st.session_state["tool_getTime"] = st.toggle("getCurrentTime", value=False)
    st.toggle("Re-Sync With Sharepoint", value=False, disabled=True)



    