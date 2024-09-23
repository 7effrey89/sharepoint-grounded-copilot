# sharepoint grounded copilot
 sharepoint grounded copilot. azure function to provide custom skillset to fill field in index.

A demo that extract sharepoint content through microsoft graph. 
The content is then landed as .json blobs in a blob storage account where a blob indexer from AI search will ingest all new/modified files.
A azure sql database is used as a watermark table to keep track of which sharepoint pages have been modied since the last time the AI search index was updated. 

The search index includes fields that contains meta data from the sharepoint pages, and is being populated by a custom skillset in AI search through an Azure Function.

The chat portal is made in streamlit

This is a work in progress demo, and the code to extract directly from sharepoint has not been implemented yet.

Architecture:
![image](https://github.com/user-attachments/assets/d2d15f32-62c4-4d75-9a3d-76f6f560f8c2)

Solution screenshot:
<img width="512" alt="image" src="https://github.com/user-attachments/assets/1ae2fadf-bbe8-44a1-b30c-2b6a35d9aada">
