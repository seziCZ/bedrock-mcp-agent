# Agent & MCP Server

## Overview

This project implements an **LLM-powered agent** integrated with a **Memory Control Protocol (MCP) server** to manage long-term memory. The MCP server enables the agent to:

- **Store** notable, user-specific, non-generic information.
- **Recall** contextual information relevant to a user’s query.
- Ensure memory is **impersonal, passive, and structured** for efficient retrieval.
- Maintain **strict JSON outputs** for integration with other systems.

The agent leverages MCP memory to provide more personalized and contextually aware responses over time.

---

## Architecture

+------------------+ +-------------------+
| | | |
| LLM Agent | <----> | MCP Server |
| | | |
+------------------+ +-------------------+
^
|

**Flow:**

1. The agent receives a user message.
2. The MCP server analyzes the message to determine:
   - Should the content be **stored** in memory? (`memory.store`)
   - Should a **recall** request be made for relevant stored information? (`memory.recall`)
3. MCP server returns a **strict JSON array** of memory tool calls.
4. The agent uses this information to generate contextually relevant responses.

---

## Features

- **Personalized Memory Management**
  - Stores notable user-specific info in **impersonal, passive form**.
  - Recalls previously stored memory only when **directly relevant**.
  
- **Strict JSON Interface**
  - All tool calls (`memory.store`, `memory.recall`) are returned in a **parseable JSON array**.
  - For general knowledge or trivial queries, returns `[]`.

- **Broad-Context Recall**
  - When recalling, the MCP server generates **generic context phrases** to ensure all relevant memory can be retrieved, even if the exact value is unknown.

- **Privacy-Compliant**
  - Memory is stored **only with user consent**.
  - General knowledge and widely-known facts are never stored.

---
