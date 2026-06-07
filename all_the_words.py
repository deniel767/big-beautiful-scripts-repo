import datetime
import os
import pickle
import tkinter as tk
from tkinter import ttk
import requests
import nest_asyncio
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv()

PICKLE_JARS = os.getenv("ATW_PICKLE_PATH", "./pickle_storage")
DEFAULT_TIMER_MS = 20000

if not os.path.exists(PICKLE_JARS):
    os.makedirs(PICKLE_JARS)

saved_words_file = os.path.join(PICKLE_JARS, "saved_words.txt")
if not os.path.exists(saved_words_file):
    with open(saved_words_file, "w", encoding="utf-8") as f:
        f.write(f"This file was originally created at {datetime.datetime.now()}\n")


def display_word_info(word_name, word_info):
    if not word_info:
        return "No data available."

    if isinstance(word_info, str):
        return f"WORD: {word_name.upper()}\n" + "=" * 30 + f"\n\nTranslation/Meaning:\n{word_info}"

    try:
        entry = word_info[0]
        output_str = f"WORD: {word_name.upper()}\n" + "=" * 30 + "\n\n"
        
        phonetic = entry.get('phonetic', '')
        if phonetic:
            output_str += f"Pronunciation: {phonetic}\n\n"

        output_str += "Definitions:\n"
        meanings = entry.get('meanings', [])
        
        for meaning in meanings:
            part_of_speech = meaning.get('partOfSpeech', 'Unknown')
            output_str += f"\n[{part_of_speech.upper()}]\n"
            definitions = meaning.get('definitions', [])
            for i, dfn in enumerate(definitions[:3], 1):
                definition_text = dfn.get('definition', '')
                output_str += f"  {i}. {definition_text}\n"
                example = dfn.get('example', '')
                if example:
                    output_str += f"     Example: \"{example}\"\n"
        return output_str
    except Exception:
        return f"WORD: {word_name.upper()}\n" + "=" * 30 + f"\n\nData:\n{str(word_info)}"

def word_lookup(word_to_lookup, language):
    word_clean = word_to_lookup.strip().lower()
    lang_clean = language.strip().lower()
    
    filename = f"{word_clean}_{lang_clean}.pkl"
    file_path = os.path.join(PICKLE_JARS, filename)

    if os.path.exists(file_path):
        print(f"[CACHE] Instant local backup found for: {word_clean}")
        with open(file_path, "rb") as file:
            word_info = pickle.load(file)
            popup_message(display_word_info(word_to_lookup, word_info), DEFAULT_TIMER_MS)
        return word_info

    print(f"[API] Querying active network records for: '{word_clean}'...")
    
    # need to specify language ID for url search as well
    # which unfortunately means hardcoding
    if lang_clean in ["romanian", "română", "ro"]:
        api_url = f"https://api.mymemory.translated.net/get?q={word_clean}&langpair=ro|en"
    else:
        api_url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word_clean}"
    
    headers = {'User-Agent': 'PortfolioGlossaryApp/1.0'}

    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 404:
            print(f"[WARNING] API returned 404: '{word_clean}' not found.")
            popup_message(f"The word '{word_to_lookup}' was not found in the database.", 4000)
            return None
            
        response.raise_for_status()
        raw_payload = response.json()
        
        # Parse based on API used
        if "mymemory" in api_url:
            word_info = raw_payload.get("responseData", {}).get("translatedText", "No translation found.")
        else:
            word_info = raw_payload
        
    except Exception as e:
        print(f"[ERROR] Network exception: {e}")
        popup_message("A network error occurred while querying the dictionary.", 4000)
        return None

    if word_info:
        print(f"[SUCCESS] Caching payload file: {filename}")
        with open(file_path, "wb") as file:
            pickle.dump(word_info, file)
            
        popup_message(display_word_info(word_to_lookup, word_info), DEFAULT_TIMER_MS)
        return word_info

def popup_message(message, timer_ms):
    popup = tk.Toplevel(root)
    popup.title("Word Details")
    
    label = tk.Label(popup, text=message, justify="left", font=("Courier", 10))
    label.pack(padx=20, pady=20)
    
    popup.update_idletasks()
    popup.after(timer_ms, popup.destroy)

def on_combobox_select(event):
    selected_item = combobox.get()
    if not selected_item or ", " not in selected_item:
        return
        
    word, language = selected_item.split(', ')
    filename = f"{word}_{language}.pkl"
    file_path = os.path.join(PICKLE_JARS, filename)
    
    if os.path.exists(file_path):
        with open(file_path, "rb") as file:
            word_info = pickle.load(file)
        popup_message(display_word_info(word, word_info), DEFAULT_TIMER_MS)

def on_text_box_input(event):
    user_input = text_box.get().strip()
    if not user_input or ' ' not in user_input:
        popup_message("Please enter the word and language separated by a space!\n(e.g., apple English)\nThen press enter.", 4000)
        return
        
    split_data = user_input.split(' ', 1)
    word_to_lookup = split_data[0]
    language = split_data[1]
    
    word_lookup(word_to_lookup, language)
    combobox_update(combobox)

def combobox_update(cb):
    raw_items = os.listdir(PICKLE_JARS)
    formatted_items = []
    
    for item in raw_items:
        if item.endswith(".pkl") and "_" in item:
            base_name = item[:-4]
            parts = base_name.split('_', 1)
            formatted_items.append(f"{parts[0]}, {parts[1]}")
            
    cb['values'] = formatted_items

# main window
root = tk.Tk()
root.title("Vocabulary & Dictionary Lookup")
root.geometry("450x250")

combobox_label = tk.Label(root, text="Collection of previously saved words:", pady=5)
combobox_label.pack()

combobox = ttk.Combobox(root, width=35)
combobox.bind("<<ComboboxSelected>>", on_combobox_select)
combobox.pack(pady=5)

text_box_label = tk.Label(root, text="Search for a word and language (e.g., 'apple English'):\nThen press enter", pady=5)
text_box_label.pack()

text_box = tk.Entry(root, width=38)
text_box.focus_set()
text_box.bind("<KeyPress-Return>", on_text_box_input)
text_box.pack(pady=5)

result_label = tk.Label(root, text="", pady=5)
result_label.pack()

combobox_update(combobox)
root.mainloop()