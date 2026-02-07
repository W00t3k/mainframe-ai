# Services (`app/services/`)

Business logic services separated from route handlers.

## Service Modules

### `chat.py`
Chat message processing and conversation management:
- Message history tracking
- RAG context integration
- Agentic tool-calling loop

### `ollama.py`
Ollama LLM client wrapper:
- Model status checking
- Chat completion requests
- Embedding generation
- Streaming support

## Design Pattern

Services are stateless functions that can be imported by route handlers. This separation allows:
- Easier unit testing
- Code reuse across routes
- Clear separation of concerns
