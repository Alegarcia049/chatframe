
# ChatFrame: AI-Powered Business Assistant

**A modular AI assistant backend for business analytics, conversational agents, and multichannel messaging integration.**

ChatFrame is a Python-based backend project designed to help small and medium-sized businesses interact with their operational data through natural language.

The system combines LangGraph-based AI agents, database querying tools, and a FastAPI backend to process business questions and generate context-aware responses.

The architecture also explores asynchronous message processing and integrations with WhatsApp, Instagram, and Facebook Messenger.

**Development status:** Prototype under active development. Some integrations and runtime components are not yet production-ready.

## Architecture

ChatFrame is organized around a modular architecture that separates API endpoints, AI agent execution, business tools, messaging channels, and background processing.

The intended message processing workflow consists of:

1. Receiving messages through an API or messaging webhook.
2. Normalizing incoming messages into a common format.
3. Queuing messages for asynchronous processing.
4. Executing an AI agent with access to business data.
5. Generating responses using an LLM.
6. Routing responses through the appropriate messaging channel.
7. Recording processing events and audit information.

The repository implements these architectural components, although some integrations remain incomplete.

## Methodology

### 1. AI Agent with LangGraph

The conversational agent is implemented using LangGraph and LangChain.

The architecture includes:

- State-based conversational workflows.
- Tool calling for business data retrieval.
- Conversational context management.
- Conditional execution of tools.
- Streaming response generation.
- LLM integration using Google's Gemini models.

The agent is designed to answer business-related questions by retrieving information from structured data sources rather than relying exclusively on model-generated knowledge.

### 2. Business Analytics Tools

Custom Python tools provide access to business metrics stored in SQLite.

The implemented tools include:

- **Monthly Sales Summary:** Retrieves current monthly sales and compares them with a predefined target.
- **Sales Comparison:** Calculates changes in sales between the current and previous months.
- **Expense Analysis:** Identifies the highest expense categories.
- **Variance Explanation:** Provides predefined contextual explanations for selected financial variations.

These tools demonstrate how language models can interact with structured databases to support business analysis.

The repository includes synthetic business data generation for development and experimentation.

### 3. FastAPI Backend

FastAPI provides the backend interface for the assistant.

The implementation includes:

- Application lifecycle management.
- Agent initialization and shutdown.
- Health-check endpoint.
- WebSocket-based chat communication.
- Streaming AI responses.
- API routing for messaging integrations.
- Application logging and error handling.

The backend separates the conversational interface from the agent's internal logic.

### 4. Multichannel Messaging Architecture

The project includes integration components for:

- WhatsApp Business.
- Instagram Messaging.
- Facebook Messenger.

A unified channel abstraction is used to normalize messages and route outgoing responses.

The Meta webhook module implements:

- Webhook verification.
- Incoming payload parsing.
- Message normalization.
- Identification of unsupported message types.
- Message metadata extraction.
- Queue-based message processing.

**Current limitation:** Outbound messaging clients are logging stubs. Integration with the corresponding Meta Graph API endpoints is not yet complete.

### 5. Asynchronous Processing

A background worker architecture is implemented to process incoming messages independently of HTTP requests.

The system includes:

- In-memory and Redis-backed message queues.
- Message deduplication.
- Retry handling with exponential backoff.
- Dead-letter queues for failed messages.
- Processing status tracking.
- Message-level trace identifiers.

This design provides a foundation for more reliable asynchronous message handling.

### 6. Database and Audit System

ChatFrame uses two database components:

**SQLite**
- Stores synthetic sales, expenses, and customer records.
- Supports business analytics queries.
- Maintains basic conversation interaction logs.

**PostgreSQL**
- Provides an optional structured audit logging system.
- Records message processing events.
- Tracks errors, retries, and processing latency.
- Stores metadata associated with message activity.

The database layer is separated from the AI agent and messaging interfaces.

### 7. Testing and Validation

The repository includes automated tests for Meta webhook payload parsing.

The tests cover:

- WhatsApp text message parsing.
- Facebook Messenger message normalization.
- Instagram message normalization.
- Handling of non-text messaging events.

Further integration and end-to-end testing would be required before production deployment.

## Technologies

- Python
- FastAPI
- LangGraph
- LangChain
- Google Gemini
- SQLite
- PostgreSQL
- Redis
- WebSockets
- Uvicorn
- Pytest

## Project Structure

~~~text
.
├── agents/
│   ├── langgraph_runtime.py
│   └── prompts.py
├── api/
│   └── v1/
│       └── meta_webhook.py
├── channels/
│   ├── base.py
│   ├── router.py
│   ├── whatsapp.py
│   ├── instagram.py
│   └── facebook.py
├── db/
│   ├── audit.py
│   ├── audit_repo.py
│   └── session.py
├── llm/
│   ├── base.py
│   ├── factory.py
│   └── gemini.py
├── tools/
│   └── langgraph_tools.py
├── worker/
│   ├── queue.py
│   ├── tasks.py
│   └── meta_client.py
├── tests/
│   └── test_meta_webhook_parsing.py
├── database.py
├── seed.py
├── settings.py
├── main.py
├── AGENTS.md
└── PLANS.md
~~~

## Running the Project

The backend entry point is located in:

`main.py`

The current repository is a development prototype and does not include a complete dependency manifest or reproducible deployment configuration.

The source code imports modules through the `app2` package namespace, so the package structure and runtime configuration must be aligned before launching the application independently.

The agent requires an appropriate LLM provider configuration. The LangGraph runtime currently supports Gemini through the LangChain Google Generative AI integration.

Other components, including PostgreSQL auditing and Redis queues, require their respective services and environment settings.

The repository should therefore be treated as an architectural prototype rather than a ready-to-deploy application.
