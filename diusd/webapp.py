import streamlit as st
from dotenv import load_dotenv

load_dotenv(".env")

pages = {
    "First Page": [
        st.Page(
            "ui/di.py",
            title="DI USD",
            icon=":material/real_estate_agent:",
        ),
    ]
}

page = st.navigation(pages)
page.run()
