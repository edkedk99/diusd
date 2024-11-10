from datetime import datetime

import pandas as pd
import requests


def sgs(cod: int, inicio: datetime | None = None, final: datetime | None = None):
    url = f"http://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados"

    params = {}
    if inicio:
        params["dataInicial"] = inicio.strftime("%d/%m/%Y")
    if final:
        params["dataFinal"] = final.strftime("%d/%m/%Y")

    res = requests.get(url, params=params)
    dados = res.json()
    df = pd.DataFrame(dados)
    df["data"] = pd.to_datetime(df.data, format="%d/%m/%Y")
    df = df.set_index("data", drop=True)
    df = df.astype(float)
    return df
