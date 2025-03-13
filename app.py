#: check all installed packages.
import sys
print("Python version:")
print(sys.version)
#
# import pkg_resources
# installed_packages = [pkg.key for pkg in pkg_resources.working_set]
# print("Packages from", sys.path)
# print(installed_packages)
# #
# import subprocess
# # Run pip list command
# result = subprocess.run(['pip', 'list'], stdout=subprocess.PIPE)
# print(result.stdout.decode('utf-8'))
#
# # move the term like this "'/tmp/8dd4a6c787463f2/antenv/lib/python3.11/site-packages'" built by oryx to be 0 index of
# # sys.path variable, i.e., the library paths.
# try:
#     sys.path.insert(0, sys.path.pop(sys.path.index(next(filter(lambda x: "antenv" in x, sys.path)))))
# except:
#     pass
# print("After reordering library path loading order, now we have Packages from", sys.path)
#
# import subprocess
# # Run pip list command
# result = subprocess.run(['pip', 'list'], stdout=subprocess.PIPE)
# print(result.stdout.decode('utf-8'))

# -----app script formally start here--------
import os
# import openai
# from langchain_openai import AzureOpenAI
# from azure.identity import DefaultAzureCredential
# from azure.keyvault.secrets import SecretClient
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType

# print(openai.__version__)
#
# # Replace with your Key Vault name
# KVUri = "https://dfci-key-vault.vault.azure.net/"
# secretName = "AZURE-OPENAI-API-KEY"
#
# # Authenticate and create a client
# credential = DefaultAzureCredential()
# client = SecretClient(vault_url=KVUri, credential=credential)
# # get secret
# retrieved_secret = client.get_secret(secretName)
# print(retrieved_secret)

# Azure OpenAI
# DONE: secure api_key by using one of the secret scope in Azure or databricks
#api_key = os.environ['AZURE_OPENAI_API_KEY'] = retrieved_secret.value

#: plan B, use fernet mechanism to decode.
from cryptography.fernet import Fernet
# Read the key from the file
with open("./static/fernet/fernet_key.txt", "rb") as key_file:
    key = key_file.read()

# Instantiate a Fernet instance with the key
cipher_suite = Fernet(key)

# Read the encrypted data from the file
with open("./static/fernet/encrypted_key.txt", "rb") as file:
    encrypted_data_from_file = file.read()

# Decrypt the data
decrypted_data = cipher_suite.decrypt(encrypted_data_from_file).decode()

# for AOAI service credentials
api_key = os.environ['AZURE_OPENAI_API_KEY'] = decrypted_data
# api_version = os.environ['AZURE_OPENAI_API_VERSION'] = "2024-10-01" # from Resource JSON in the portal of the specific Azure OpenAI page.
api_version = os.environ[
    'AZURE_OPENAI_API_VERSION'] = "2024-05-01-preview"  # from Chat playground Sample Code (key authentication)
azure_deployment = os.environ['AZURE_OPENAI_ENDPOINT'] = "https://dfci-aoai-test.openai.azure.com/"
model_name = os.environ['AZURE_OPENAI_MODEL_NAME'] = "gpt-4o"

# for Azure (Cognitive) AI search service credentials
os.environ["AZURE_SEARCH_ENDPOINT"] = "https://dfci-demo-ai-search.search.windows.net" # use url
os.environ["AZURE_SEARCH_INDEX_NAME"] = "vector-1741736011004" # use index name
os.environ["AZURE_SEARCH_API_KEY"]  # please use query key instead of admin key; being setup under fernet-w-api-rag
# (dfci-demo-app/fernet-w-api-rag) | Environment variables

# make sure we have flask >3.0. In runtime ML 15.4, it is old version of flask, so will fail.
from flask import (Flask, redirect, render_template, request, send_from_directory, url_for)

app = Flask(__name__)


@app.route('/')
def index():
    print('Request for index page received')
    return render_template('index.html')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico',
                               mimetype='image/vnd.microsoft.icon')


@app.route('/api/hello', methods=['POST'])
def hello():
    req = request.form.get('req')

    # Azure OpenAI
    client = AzureOpenAI(api_key=os.getenv("AZURE_OPENAI_API_KEY"), api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"))

    # Azure AI Search
    search_client = SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY"))
    )

    user_input = req

    # Query Azure Cognitive Search
    search_results = search_client.search(
        search_text=user_input,
        query_type="semantic",
        top=5  # Adjust the number of results as needed
    )
    print(search_results)
    # Extract relevant information from search results
    search_content = "\n".join([result["chunk"] for result in search_results])
    print("search_content:", search_content)

    # Create the chat prompt with search results
    chat_prompt = [
        {"role": "system", "content": "Scan the stock market to recommend stocks with strong fundamentals and technical indicators that indicate a good buy price. Provide comprehensive analysis incorporating fundamental data, technical indicators, and market sentiment. Given the complexity of this task, prioritize delivering depth over the total number of stock analyses offered. Recommended output can reasonably focus on 2-3 stocks."},
        {"role": "user", "content": f"According to additional real-time context info identified: {search_content} \n\n please combine the context and answer my question: {user_input}."},
        {"role": "assistant", "content": [{"type": "text", "text": ""}]}
    ]

    messages = chat_prompt

    try:
        completion = client.chat.completions.create(model=model_name, messages=messages, max_tokens=4096, temperature=0.7,
            top_p=0.95, frequency_penalty=0, presence_penalty=0, stop=None, stream=False)
        text = completion.choices[0].message.content
    except Exception as e:
        print(f"Error during completion: {e}")
        text = "An error occurred while processing your request."

    if req:
        print('Request for hello page received with req=%s' % req)
        return render_template('hello.html', req=text)
    else:
        print('Request for hello page received with no name or blank name -- redirecting')
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
