from datetime import date, datetime

import pandas as pd
import streamlit as st
from requests.exceptions import JSONDecodeError
import os
from diusd.web import di

file_path = os.getenv("DIUSD_FILE_PATH")
if not file_path:
    st.error("Dados nao encontrados")
    st.stop()


data = di.load_data(file_path)
if data.df.empty:
    st.error("Dados não baixados")
    st.stop()


first_dt_name = data.df.iloc[0].name
assert isinstance(first_dt_name, pd.Timestamp)
first_dt = first_dt_name.date()
last_dt_name = data.df.iloc[-1].name
assert isinstance(last_dt_name, pd.Timestamp)
last_dt = last_dt_name.date()


start_field = st.date_input(
    "Inicio",
    value=first_dt,
    min_value=first_dt,
    max_value=last_dt,
)
end_field = st.date_input(
    "Final",
    value=last_dt,
    min_value=first_dt,
    max_value=last_dt,
)
assert isinstance(start_field, date)
assert isinstance(end_field, date)

start_dt = datetime(start_field.year, start_field.month, start_field.day)  # pyright: ignore
end_dt = datetime(end_field.year, end_field.month, end_field.day)  # pyright: ignore

rets = di.DiDolReturn(data.df, start_dt, end_dt)

period_col1, period_col2 = st.columns(2)
period_col1.metric("Dias Uteis", rets.dias)
period_col2.metric("Anos", f"{rets.dias / 252:,.2f}")


inicio_dt = rets.period_df.iloc[0].name
assert isinstance(inicio_dt, date)
final_dt = rets.period_df.iloc[-1].name
assert isinstance(final_dt, date)

st.subheader("Cotação")
usd_table = rets.get_cotacao_table()
st.dataframe(usd_table)

st.subheader("Rentabilidade")
rentab_table = rets.get_returns_table()
st.dataframe(rentab_table)