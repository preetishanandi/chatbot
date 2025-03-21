import streamlit as st
import ollama
import pdfplumber
import pandas as pd
import os
import time
import json
import speech_recognition as sr
import pyttsx3
import threading
import re
from datetime import datetime, timedelta

# File to store chat history
CHAT_HISTORY_FILE = "chat_sessions.json"

# Function to remove emojis from text
def remove_emojis(text):
    emoji_pattern = re.compile("["  
        u"\U0001F600-\U0001F64F"  # Emoticons
        u"\U0001F300-\U0001F5FF"  # Symbols & Pictographs
        u"\U0001F680-\U0001F6FF"  # Transport & Map Symbols
        u"\U0001F700-\U0001F77F"  # Alchemical Symbols
        u"\U0001F780-\U0001F7FF"  # Geometric Shapes
        u"\U0001F800-\U0001F8FF"  # Supplemental Arrows
        u"\U0001F900-\U0001F9FF"  # Supplemental Symbols
        u"\U0001FA00-\U0001FA6F"  # Chess Symbols
        u"\U0001FA70-\U0001FAFF"  # Miscellaneous Symbols
        u"\U00002702-\U000027B0"  # Dingbats
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

# Function to initialize and restart text-to-speech engine
def speak_text(text):
    def _speak():
        tts_engine = pyttsx3.init()
        tts_engine.say(remove_emojis(text))  # Remove emojis before speaking
        tts_engine.runAndWait()
        tts_engine.stop()
    thread = threading.Thread(target=_speak)
    thread.start()

# Initialize speech recognizer
recognizer = sr.Recognizer()

def get_voice_input():
    """Capture voice input from the microphone and return recognized text."""
    with sr.Microphone() as source:
        st.info("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=5)
            return recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            st.warning("Sorry, could not understand audio.")
        except sr.RequestError:
            st.warning("Could not request results, check your internet.")
        except Exception as e:
            st.warning(f"Error: {str(e)}")
    return ""

# Load chatbot model
@st.cache_resource
def load_model():
    return "tinyllama"

chatbot = load_model()

# Function to load chat history
def load_chat_sessions():
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, "r") as file:
            return json.load(file)
    return {}

# Function to save chat history
def save_chat_sessions(sessions):
    with open(CHAT_HISTORY_FILE, "w") as file:
        json.dump(sessions, file)

# Load existing chat sessions
chat_sessions = load_chat_sessions()

# Categorize chats (Today, Yesterday, Previous 7 Days, Previous 30 Days)
today = datetime.today().date()
yesterday = today - timedelta(days=1)
seven_days_ago = today - timedelta(days=7)
thirty_days_ago = today - timedelta(days=30)

today_chats = {}
yesterday_chats = {}
past_week_chats = {}
past_month_chats = {}

for session_id, session in chat_sessions.items():
    chat_date = datetime.strptime(session["date"], "%Y-%m-%d").date()
    if chat_date == today:
        today_chats[session_id] = session
    elif chat_date == yesterday:
        yesterday_chats[session_id] = session
    elif seven_days_ago <= chat_date < yesterday:
        past_week_chats[session_id] = session
    elif thirty_days_ago <= chat_date < seven_days_ago:
        past_month_chats[session_id] = session

# Streamlit Sidebar (Chat History)
st.sidebar.title("💬 InfoFlow")

# File uploader (supports multiple files)
uploaded_files = st.sidebar.file_uploader("📂 Upload Documents", accept_multiple_files=True, type=["pdf", "csv", "xlsx"])

# "New Chat" Button
if st.sidebar.button("➕ New Chat"):
    st.session_state["current_chat_id"] = None
    st.session_state["messages"] = []

# Search Bar
search_query = st.sidebar.text_input("🔍 Search Chats")

# Function to display chat list with options
def display_chat_list(title, chat_dict):
    if chat_dict:
        st.sidebar.subheader(title)
        for session_id in chat_dict.keys():
            if not search_query or search_query.lower() in session_id.lower():
                with st.sidebar.expander(session_id, expanded=False):
                    if st.button("📝 Rename", key=f"rename_{session_id}"):
                        new_name = st.text_input("Enter new name", value=session_id)
                        if new_name and new_name != session_id:
                            chat_sessions[new_name] = chat_sessions.pop(session_id)
                            save_chat_sessions(chat_sessions)
                            st.rerun()

                    if st.button("📥 Archive", key=f"archive_{session_id}"):
                        chat_sessions[session_id]["archived"] = True
                        save_chat_sessions(chat_sessions)
                        st.experimental_rerun()

                    if st.button("🗑 Delete", key=f"delete_{session_id}"):
                        del chat_sessions[session_id]
                        save_chat_sessions(chat_sessions)
                        st.experimental_rerun()

                    if st.button(session_id, key=session_id):
                        st.session_state["current_chat_id"] = session_id
                        st.session_state["messages"] = chat_dict[session_id]["messages"]

display_chat_list("📌 Today", today_chats)
display_chat_list("📅 Yesterday", yesterday_chats)  # Added Yesterday Section
display_chat_list("📆 Previous 7 Days", past_week_chats)
display_chat_list("📅 Previous 30 Days", past_month_chats)

# Clear all chats button
if st.sidebar.button("🗑 Clear All Chats"):
    chat_sessions.clear()
    save_chat_sessions(chat_sessions)
    st.session_state["messages"] = []
    st.session_state["current_chat_id"] = f"Chat 1 - {today}"
    st.sidebar.success("All chat history cleared!")

# Get current chat session
if "current_chat_id" not in st.session_state or not st.session_state["current_chat_id"]:
    new_chat_id = f"Chat {len(chat_sessions) + 1} - {today}"
    st.session_state["current_chat_id"] = new_chat_id
    st.session_state["messages"] = []

# Chat interface
st.title("💬 InfoFlow.AI")
st.subheader("What can I help with?")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# User input
query = st.chat_input("Ask anything...")
if st.button("🎤 Speak"):
    query = get_voice_input()

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.write(query)

    # Process uploaded files
    file_data = ""
    if uploaded_files:
        for file in uploaded_files:
            if file.name.endswith(".pdf"):
                with pdfplumber.open(file) as pdf:
                    file_data += "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
            elif file.name.endswith((".csv", ".xlsx")):
                df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
                file_data += df.to_string()

    # Generate response
    try:
        if file_data:
            response = ollama.generate(model=chatbot, prompt=f"{file_data}\n\n{query}")
        else:
            response = ollama.generate(model=chatbot, prompt=query)
        bot_response = response.get("response", "Sorry, I couldn't generate a response.")
    except Exception as e:
        bot_response = f"Error: {str(e)}"

    # Display assistant response
    with st.chat_message("assistant"):
        st.write(bot_response)

    # Ensure the bot speaks every response (without emojis)
    speak_text(bot_response)


    # Save messages
    st.session_state.messages.append({"role": "assistant", "content": bot_response})
    chat_sessions[st.session_state["current_chat_id"]] = {"date": str(today), "messages": st.session_state.messages}
    save_chat_sessions(chat_sessions)