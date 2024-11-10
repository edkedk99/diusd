import os

import streamlit as st
from streamlit import session_state as ss


class CommonSt:
    def __init__(self) -> None:
        self.db_path = os.getenv("ST_DB_PATH")

        self.conn = None
        if bool(self.db_path):
            self.conn = st.connection("sql", url=self.db_path)

    def set_state(_self, key: str, value) -> None:
        if key not in ss:
            ss[key] = value
