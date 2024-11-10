import streamlit as st
from dotenv import load_dotenv

load_dotenv(".env")

pages = {
    "First Page": [
        st.Page(
            "ui/first_page.py",
            title="First Page",
            icon=":material/real_estate_agent:",
        ),
    ]
}

page = st.navigation(pages)
page.run()
