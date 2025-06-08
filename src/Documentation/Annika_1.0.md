# Message Processing System for MicrosoftAgencySwarm
 
## Overview
 
This document provides a comprehensive overview of the message processing system implemented for the MicrosoftAgencySwarm project. The system is designed to handle incoming messages from Microsoft Teams, process them efficiently, and integrate with an AI-powered agency for intelligent responses.
 
## System Components
 
1. **Quart Application (Quart_app.py)** - 135 lines
2. **Message Processor Tool (MessageProcessorTool.py)** - 186 lines
3. **Webhook Filter (webhook_filter.py)** - 214 lines
4. **Redis Manager (Redis.py)** - 71 lines
5. **Agency Server (agency_server.py)** - 62 lines
6. **Internal Messenger (InternalMessenger.py)** - 135 lines
 
Total Lines of Code: 803
 
## Detailed Component Descriptions
 
### 1. Quart Application (Quart_app.py) - 135 lines
 
The Quart application serves as the entry point for incoming webhooks from Microsoft Teams. It handles the following key functions:
 
- Initializes the application and sets up necessary configurations
- Provides endpoints for webhook validation and message reception
- Manages lifecycle events for the application
- Integrates with the WebhookFilter for processing incoming messages
 
**Stack Trace:**
1. Application initialization
2. Redis setup
3. Webhook endpoint handling
4. Message forwarding to WebhookFilter
5. Error handling and logging
 
### 2. Message Processor Tool (MessageProcessorTool.py) - 186 lines
 
This tool is responsible for processing individual messages received from Microsoft Teams. Its primary functions include:
 
- Retrieving detailed message information using the Microsoft Graph API
- Filtering messages based on sender information
- Preparing messages for further processing by the AI agency
- Sending processed messages to the Agency Server
 
**Stack Trace:**
1. Message details retrieval
2. Sender verification
3. Message content extraction
4. Agency Server communication
5. Response handling and logging
 
### 3. Webhook Filter (webhook_filter.py) - 214 lines
 
The WebhookFilter manages the flow of incoming messages, ensuring efficient processing and preventing duplicates. Key features include:
 
- Redis-based queue management for incoming messages
- Duplicate message detection and filtering
- Asynchronous message processing
- Load balancing across multiple instances
 
**Stack Trace:**
1. Webhook data parsing
2. Message queueing in Redis
3. Duplicate detection
4. Asynchronous queue processing
5. Message forwarding to MessageProcessorTool
 
### 4. Redis Manager (Redis.py) - 71 lines
 
The Redis Manager handles the setup and management of the Redis instance used for message queueing and state management. It provides:
 
- Automated Redis container setup using Docker
- Redis client initialization
- Connection management and error handling
 
**Stack Trace:**
1. Docker container initialization
2. Redis server startup
3. Client connection establishment
4. Error handling and logging
5. Graceful shutdown procedures
 
### 5. Agency Server (agency_server.py) - 62 lines
 
The Agency Server acts as an intermediary between the message processing system and the AI-powered agency. Its responsibilities include:
 
- Receiving processed messages from the MessageProcessorTool
- Forwarding messages to the appropriate AI agent
- Handling responses from the AI agency
- Sending responses back to Microsoft Teams
 
**Stack Trace:**
1. Server initialization
2. Client connection handling
3. Message reception and parsing
4. AI agency communication
5. Response forwarding to InternalMessenger
 
### 6. Internal Messenger (InternalMessenger.py) - 135 lines
 
The Internal Messenger facilitates communication between the Agency Server and Microsoft Teams. Its primary functions are:
 
- Authenticating with the Microsoft Graph API
- Sending messages to specific Teams chats or channels
- Handling message formatting and content types
- Error handling and logging for message delivery
 
**Stack Trace:**
1. Microsoft Graph API authentication
2. Message preparation and formatting
3. API request construction
4. Message sending to Teams
5. Response handling and error management
 
## System Flow
 
1. Incoming webhook received by Quart Application
2. WebhookFilter processes and queues the message
3. MessageProcessorTool retrieves message details and prepares for processing
4. Agency Server receives the processed message
5. AI agency generates a response
6. Internal Messenger sends the response back to Microsoft Teams
 
## Key Features
 
- **Scalability**: The system is designed to handle multiple instances and high message volumes.
- **Reliability**: Redis-based queueing ensures message persistence and prevents data loss.
- **Efficiency**: Asynchronous processing and duplicate detection optimize resource usage.
- **Flexibility**: The modular design allows for easy integration with different AI agencies and messaging platforms.
- **Security**: Proper authentication and access token management ensure secure communication with Microsoft services.
 
## Conclusion
 
This message processing system provides a robust, scalable, and efficient solution for handling Microsoft Teams messages and integrating with AI-powered agencies. Its modular design and use of modern technologies make it an ideal choice for businesses looking to enhance their communication and automation capabilities. With a total of 803 lines of code across six well-structured components, the system demonstrates a balance between complexity and maintainability, showcasing the potential for significant impact with a relatively compact codebase.
 
# Microsoft Agency Swarm Integration
 
This project integrates Microsoft Teams with the Agency Swarm framework, providing a robust system for handling webhooks, managing OAuth 2.0 authentication, and maintaining access tokens for Microsoft Graph API interactions.
 
## Key Components
 
### 1. BootApp.py (89 lines)
 
The main entry point for starting all components of the integration.
 
Key features:
- Manages the startup sequence of all components
- Starts NGROK, MS_ACCESS_AUTO, OAuth2 Delegate, Quart application, and Subscription Manager
- Implements graceful shutdown of all processes
 
### 2. Quart_app.py (135 lines)
 
Sets up a Quart web server to handle incoming webhooks from Microsoft Teams.
 
Key features:
- Handles webhook validation requests
- Processes incoming messages using the MessageProcessorTool
- Integrates with the subscription manager for subscription handling
- Uses Redis for caching and concurrency control
 
Main routes:
- `/api/webhook`: Handles incoming webhooks from Microsoft Teams
- `/api/lifecycle`: Manages subscription lifecycle events
 
### 3. MessageProcessorTool.py (186 lines)
 
Processes incoming Teams messages and prepares them for the AgencyServer.
 
Key features:
- Extends the BaseTool class from the Agency Swarm framework
- Parses webhook data and extracts message details
- Retrieves full message content using Microsoft Graph API
- Sends processed messages to the AgencyServer
- Uses Redis for caching processed messages
 
### 4. Boot_NGROK.py (71 lines)
 
Responsible for starting and managing the ngrok tunnel.
 
Key features:
- Starts the ngrok process to create a secure tunnel to localhost
- Checks if ngrok is already running
- Retrieves and logs the active ngrok tunnels
 
### 5. Qauth2Delegate.py (262 lines)
 
Manages OAuth 2.0 authentication for both application and user access to Microsoft Graph API.
 
Key features:
- Implements app-only and user-delegated authentication flows
- Sets up a local HTTP server to handle OAuth 2.0 redirect
- Updates the .env file with new tokens and refresh tokens
 
### 6. MS_ACCESS_AUTO.py (110 lines)
 
Automates the process of refreshing access tokens for application access to Microsoft Graph API.
 
Key features:
- Periodically retrieves new access tokens using client credentials flow
- Updates the .env file with the new access token and user scopes
- Retrieves and updates the user ID using the Graph API
 
### 7. Redis.py (71 lines)
 
Manages the Redis connection and provides a client for other components.
 
Key features:
- Manages the Redis Docker container
- Initializes the Redis client
- Provides functions for setting up and shutting down Redis
 
## Getting Started
 
1. Set up environment variables in the `.env` file.
2. Install dependencies: `pip install -r requirements.txt`
3. Run the main startup script: `python MicrosoftAgencySwarm/TeamsAgent/Utils/BootApp.py`
 
## Workflow
 
1. BootApp.py initiates all components in sequence.
2. Quart_app.py receives webhooks from Microsoft Teams.
3. MessageProcessorTool processes incoming messages and sends them to the AgencyServer.
4. Subscription Manager ensures active subscriptions to Teams notifications.
5. MS_ACCESS_AUTO refreshes tokens periodically.
6. The TeamsAgent processes messages and generates responses.
 
## Troubleshooting
 
- Check ngrok URLs in the .env file if webhooks are not received.
- Verify authentication credentials in the .env file for auth issues.
- Ensure Docker is running for Redis-related problems.
- Check component logs for detailed error information.
 
## Security Considerations
 
- Keep the .env file secure and out of version control.
- Protect ngrok URLs.
- Ensure proper Redis security, especially in production.
 
This system provides a comprehensive solution for integrating Microsoft Teams with the Agency Swarm framework, handling authentication, webhook processing, and maintaining persistent connections.
 