import re
def clean_text(text):
    text=text.replace("\x00"," ")
    text=re.sub(r"[ \t]+"," ",text)
    text=re.sub(r"\n{3,}","\n\n",text)
    return text.strip()
