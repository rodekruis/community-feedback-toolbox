# Community Feedback Toolbox

A simple web app to help CEA officers analyze community feedback data.
https://community-feedback-toolbox.azurewebsites.net/

## Description

Synopsis: a [flask python app](https://flask.palletsprojects.com/en/2.0.x/).

Workflow: upload community feedback data, select or upload a coding framework, analyze data, download results.

## Requirements

1. [Azure Account](https://signup.azure.com/)
2. [Azure SQL database](https://azure.microsoft.com/en-us/products/azure-sql/database)
3. [Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/introduction)

## Setup

1. [Deploy the web app to Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/quickstart-python)
3. Add necessary keys to connect to databases. From Azure Portal, App Service > Configuration > New application setting
```
SQL_USERNAME=...
SQL_PASSWORD=...
COSMOS_KEY=...
MODE=online
```
