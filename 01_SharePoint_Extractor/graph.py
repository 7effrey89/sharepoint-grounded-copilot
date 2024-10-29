# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# <UserAuthConfigSnippet>
from configparser import SectionProxy
from azure.identity import DeviceCodeCredential
from msgraph import GraphServiceClient
from msgraph.generated.users.item.user_item_request_builder import UserItemRequestBuilder
from msgraph.generated.users.item.mail_folders.item.messages.messages_request_builder import (
    MessagesRequestBuilder)
from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
    SendMailPostRequestBody)
from msgraph.generated.models.message import Message
from msgraph.generated.models.item_body import ItemBody
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.recipient import Recipient
from msgraph.generated.models.email_address import EmailAddress

from msgraph.generated.sites.sites_request_builder import SitesRequestBuilder
from kiota_abstractions.base_request_configuration import RequestConfiguration
from msgraph.generated.sites.item.pages.pages_request_builder import PagesRequestBuilder
from msgraph.generated.sites.item.pages.item.graph_site_page.graph_site_page_request_builder import GraphSitePageRequestBuilder

class Graph:
    settings: SectionProxy
    device_code_credential: DeviceCodeCredential
    user_client: GraphServiceClient

    def __init__(self, config: SectionProxy):
        self.settings = config
        client_id = self.settings['clientId']
        tenant_id = self.settings['tenantId']
        graph_scopes = self.settings['graphUserScopes'].split(' ')

        self.device_code_credential = DeviceCodeCredential(client_id, tenant_id = tenant_id)
        self.user_client = GraphServiceClient(self.device_code_credential, graph_scopes)
# </UserAuthConfigSnippet>

    # <GetUserTokenSnippet>
    async def get_user_token(self):
        graph_scopes = self.settings['graphUserScopes']
        access_token = self.device_code_credential.get_token(graph_scopes)
        return access_token.token
    # </GetUserTokenSnippet>

    # <GetUserSnippet>
    async def get_user(self):
        # Only request specific properties using $select
        query_params = UserItemRequestBuilder.UserItemRequestBuilderGetQueryParameters(
            select=['displayName', 'mail', 'userPrincipalName']
        )

        request_config = UserItemRequestBuilder.UserItemRequestBuilderGetRequestConfiguration(
            query_parameters=query_params
        )

        user = await self.user_client.me.get(request_configuration=request_config)
        return user
    # </GetUserSnippet>

    # <GetInboxSnippet>
    async def get_inbox(self):
        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            # Only request specific properties
            select=['from', 'isRead', 'receivedDateTime', 'subject'],
            # Get at most 25 results
            top=25,
            # Sort by received time, newest first
            orderby=['receivedDateTime DESC']
        )
        request_config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            query_parameters= query_params
        )

        messages = await self.user_client.me.mail_folders.by_mail_folder_id('inbox').messages.get(
                request_configuration=request_config)
        return messages
    # </GetInboxSnippet>

    # <SendMailSnippet>
    async def send_mail(self, subject: str, body: str, recipient: str):
        message = Message()
        message.subject = subject

        message.body = ItemBody()
        message.body.content_type = BodyType.Text
        message.body.content = body

        to_recipient = Recipient()
        to_recipient.email_address = EmailAddress()
        to_recipient.email_address.address = recipient
        message.to_recipients = []
        message.to_recipients.append(to_recipient)

        request_body = SendMailPostRequestBody()
        request_body.message = message

        await self.user_client.me.send_mail.post(body=request_body)
    # </SendMailSnippet>

    # <MakeGraphCallSnippet>
    async def make_graph_call(self):

        #find site
        query_params = SitesRequestBuilder.SitesRequestBuilderGetQueryParameters(
		    search = 'MyFirstSharepointSite',
            select = ["id","name","weburl","lastModifiedDateTime"]
        )

        request_configuration = RequestConfiguration(
            query_parameters = query_params,
        )

        Site = await self.user_client.sites.get(request_configuration = request_configuration)
        # print(Site)

        siteID = Site.value[0].id #id='m365x02897599.sharepoint.com,f5396752-1681-4405-a5ea-67370e80ad4a,ea9206ea-7449-4481-9034-23b3b6c36ff4'
        siteLastModifiedDateTime = Site.value[0].last_modified_date_time #DateTime(2024, 9, 12, 7, 39, 20, tzinfo=Timezone('UTC'))
        siteName = Site.value[0].name #name='MyFirstSharePointSite'
        siteUrl = Site.value[0].web_url #weburl='https://m365x02897599.sharepoint.com/sites/MyFirstSharePointSite'

        #overview of pages in the site:
        query_params = PagesRequestBuilder.PagesRequestBuilderGetQueryParameters(
		select = ["id","name","title","weburl","lastModifiedDateTime"],
        )

        request_configuration = RequestConfiguration(
            query_parameters = query_params,
        )

        Pages = await self.user_client.sites.by_site_id(siteID).pages.get(request_configuration = request_configuration)
        # print(Pages)
        pages_list = []

        for page in Pages.value:
            # get page content
            query_params = GraphSitePageRequestBuilder.GraphSitePageRequestBuilderGetQueryParameters(
            expand = ["canvasLayout"],
            )

            request_configuration = RequestConfiguration(
                query_parameters = query_params,
            )

            result = await self.user_client.sites.by_site_id(siteID).pages.by_base_site_page_id(page.id).graph_site_page.get(request_configuration = request_configuration)

            page_details = {
                "Page_ID": page.id,
                "Page_Name": page.name,
                "Page_Title": page.title,
                "Page_URL": page.web_url,
                "Last_Modified": page.last_modified_date_time,
                "Page_Description"  : result.description,
                "Page_CanvasLayout" : result.canvas_layout
            }
            
            print(f"Page Title: {page.title}")
            print(f"Page URL: {page.web_url}")
            print(f"Description: {result.description}")
            print(f"Last Modified Date: {page.last_modified_date_time}")
            print(f"Canvas Layout: {result.canvas_layout}")

            #append to  a list
            pages_list.append(page_details)

        return None
    
    # </MakeGraphCallSnippet>
