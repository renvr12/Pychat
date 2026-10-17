==============================================================================
                                   PyChat
==============================================================================

OVERVIEW
--------
PyChat is a lightweight, open-source, retro-futuristic desktop terminal
designed for local AI character roleplay. Built with Python and Pygame, it connects
seamlessly to local OpenAI-compatible LLM engines (such as LM Studio), offering
dynamic relationship tracking, central universe lore injection, and a portable
.chat character packaging system.


KEY FEATURES
------------
* First-Time Setup Wizard: Zero hardcoded persona dependencies. Fresh installations
  launch directly into an interactive setup wizard to create your operator identity
  and initial AI companion.
* Portable .chat Character Packages: Bundles character personalities, baseline trust
  settings, and universe lore into a single shareable .chat file.
* Dynamic Relationship System: Sentiment analysis tracks dialogue context to
  dynamically increase or decrease relationship trust levels in real-time.
* Global Universe Lore Injection (lore.txt): Centralized lore database dynamically
  injects universe-wide context into system prompts on every conversation turn.
* Retro Sci-Fi Visuals & Audio: Features CRT monitor scanlines, optic glows, corner-bracket
  terminal framing, and procedurally synthesized audio fallback effects.
* 100% Offline & Private: Connects directly to local OpenAI-compatible endpoints.


SYSTEM REQUIREMENTS & SETUP
---------------------------
Prerequisites:
  1. Python 3.10+
  2. Pygame / Pygame-ce
  3. OpenAI Python SDK
  4. Local LLM Server (e.g., LM Studio running locally on http://localhost:1234/v1)

Quick Start:
  1. Install Python dependencies:
     pip install pygame openai

  2. Start your local LLM inference server (e.g., LM Studio) on port 1234.

  3. Run the main application script:
     python main.py


CONTROLS & KEYBINDINGS
----------------------
  Enter         : Send current message
  Shift + Enter : Insert newline in multi-line input box
  Ctrl + E      : Export active persona, relationship state, and lore as a .chat file
  Ctrl + R      : Reset active chat session & restore baseline relationship metrics
  Mouse Wheel   : Scroll through chat history or sidebar personas


PORTABLE .CHAT PACKAGE STRUCTURE
--------------------------------
The .chat format is a JSON structure saved under the custom .chat extension for
easy character sharing across users and nodes.

Example payload:
  {
    "format": "nexus_chat_package",
    "version": "1.0",
    "persona": {
      "id": "unit_01",
      "name": "Unit-01",
      "subtitle": "Autonomous AI Companion",
      "color": [0, 220, 160],
      "temperature": 0.7,
      "greeting": "*boots up optic sensors* \"System online. How can I assist you?\"",
      "base_prompt": "You are Unit-01, an autonomous digital assistant..."
    },
    "initial_trust": 50,
    "bundled_lore": "GLOBAL LORE: Terminal operating on an isolated local network node."
  }


PROJECT DIRECTORY LAYOUT
------------------------
NexusTerminal/
├── main.py              # Main application entry point & Pygame UI engine
├── lore.txt             # Central global universe context file
├── personas/            # AI character JSON profiles
├── user_personas/       # User operator JSON profiles
├── saves/               # Active chat histories & dynamic relationship metrics
├── exports/             # Output folder for exported .chat packages & logs
└── sfx/                 # Audio samples (with procedural fallback synthesizers)

ADDITIONAL INFO

------------------------
no sign-in is required unless your sharing some .chat files somewhere gay or somethin'

LICENSE
-------
Distributed under the MIT License.
==============================================================================