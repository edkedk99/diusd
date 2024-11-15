import pickle
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import cached_property
from pathlib import Path
from typing import Literal

import pandas as pd
import requests
from fredapi import Fred

from diusd.web.lib import sgs
import matplotlib.pyplot as plt
import plotly.graph_objects as go


IndexNames = Literal["usd", "di", "corp"]
AnualizaTipos = Literal["fixo", "posicao", "nenhum"]


def load_data(file_path: str):
    if not Path(file_path).exists():
        saved_data = SavedData(last_download=None, df=pd.DataFrame())
        with open(file_path, "wb") as f:
            pickle.dump(saved_data, f)

    with open(file_path, "rb") as f:
        saved_data: SavedData = pickle.load(f)

    return saved_data


@dataclass
class SavedData:
    last_download: date | None
    df: pd.DataFrame


class DiDolData:
    _LAST_DATE_SGS_CODE = 12

    def __init__(self, file_path: str, years: int = 20) -> None:
        self.file_path = file_path
        self.years = years

        yesterday = date.today() - timedelta(days=1)
        self.base_date = yesterday - timedelta(365 * self.years)

        self._saved_data = load_data(self.file_path)

        if self._need_download_all:
            print("Baixando todo o periodo")
            self._download_from_beggining()
        else:
            print("Baixando novas datas apenas")
            self._download_partial()

        new_data = load_data(self.file_path)
        self.last_download = new_data.last_download
        self.df = new_data.df

    def _save_data(self, data: SavedData):
        with open(self.file_path, "wb") as f:
            pickle.dump(data, f)

    @cached_property
    def _need_download_all(self):
        today = date.today()
        has_download = bool(self._saved_data.last_download)
        downloaded_today = self._saved_data.last_download == today
        if not has_download or not downloaded_today:
            return True

        if self._saved_data.df.empty:
            return True

        first_date_name = self._saved_data.df.iloc[0].name
        assert isinstance(first_date_name, pd.Timestamp)
        first_date = first_date_name.date()

        return first_date < self.base_date

    def _get_di_dol(self, start_date: date):
        start_dt = datetime(start_date.year, start_date.month, start_date.day)

        print("Baixando historico USD")
        df_dol = sgs(1, start_dt)
        print("Baixando historico DI")
        df_di = sgs(12, start_dt)

        fred = Fred()
        print("Baixando US IG Corporate Index")
        corp_index = fred.get_series(
            "BAMLCC0A0CMTRIV",
            observation_start=start_dt,
        )
        corp_index.name = "corp"

        df = df_di.join(df_dol, how="left", lsuffix="_di", rsuffix="_usd")
        df = df.ffill().dropna()

        corp_index = corp_index.reindex(df.index).ffill().dropna()
        df = df.join(corp_index, how="left").ffill()

        return df

    @cached_property
    def _last_date_source(self):
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{self._LAST_DATE_SGS_CODE}/dados/ultimos/1"
        res = requests.get(url)
        dados = res.json()
        data_str = dados[0]["data"]
        dt = datetime.strptime(data_str, "%d/%m/%Y").date()
        return dt

    def _download_from_beggining(self):
        df = self._get_di_dol(self.base_date)
        saved_data = SavedData(last_download=date.today(), df=df)
        self._save_data(saved_data)

    def _download_partial(self):
        last_date_name = self._saved_data.df.iloc[-1].name
        assert isinstance(last_date_name, pd.Timestamp)
        last_date = last_date_name.date()
        new_start_dt = last_date + timedelta(days=1)
        if self._last_date_source > new_start_dt:
            df_new = self._get_di_dol(new_start_dt)
            df = pd.concat([self._saved_data.df, df_new])
            new_data = SavedData(last_download=date.today(), df=df)
            self._save_data(new_data)


class DiDolReturn:
    def __init__(
        self, df_completa: pd.DataFrame, start: datetime, end: datetime
    ) -> None:
        self.df_completa = df_completa
        self.start = start
        self.end = end

        self.period_df = df_completa[
            (df_completa.index >= start) & (df_completa.index <= end)
        ]
        self.dias = self.period_df.shape[0]

    @cached_property
    def _fator_df(self):
        usd_tx = self.period_df.valor_usd
        first_usd_tx = usd_tx.iloc[0]
        usd: pd.Series = usd_tx / first_usd_tx
        usd.name = "usd"

        di = 1 + (self.period_df.valor_di / 100)
        di = di.cumprod()
        first_di = di.iloc[0]
        di = di / first_di
        di.name = "di"

        corp = self.period_df.corp
        corp.name = "corp"

        df = pd.concat([usd, di, corp], axis=1)
        return df

    def get_index_fator(self, index: IndexNames):
        start_row = self._fator_df.iloc[0]
        end_row = self._fator_df.iloc[-1]
        ret = float(end_row[index] / start_row[index])
        return ret

    def fator2return(self, fator: float):
        ret_percent = (fator - 1) * 100
        ret_str = f"{ret_percent:,.2f}%"
        return ret_str

    def get_excess_fator(self, index_return: float, benchmark_return: float):
        ret = benchmark_return / index_return - 1
        ret_percent = ret * 100
        ret_str = f"{ret_percent:,.2f}%"
        return ret_str

    def get_anual(self, fator: float):
        anual = (fator ** (252 / self.dias)) - 1
        anual = anual * 100
        anual_str = f"{anual:,.2f}%"
        return anual_str

    def to_str(self, v: float):
        v_str = f"{v:,.2f}"
        return v_str

    def get_cotacao_table(self):
        inicio_dt = self.period_df.iloc[0].name
        assert isinstance(inicio_dt, date)
        final_dt = self.period_df.iloc[-1].name
        assert isinstance(final_dt, date)

        usd_table = {
            "Data": {
                "Inicio": inicio_dt.strftime("%d/%m/%Y"),
                "Final": final_dt.strftime("%d/%m/%Y"),
            },
            "USD": {
                "Inicio": self.period_df.iloc[0]["valor_usd"],
                "Final": self.period_df.iloc[-1]["valor_usd"],
            },
        }

        return usd_table

    def get_returns_table(self):
        usd_fator = self.get_index_fator("usd")
        di_fator = self.get_index_fator("di")
        di_dol_fator = di_fator / usd_fator
        corp_fator = self.get_index_fator("corp")
        excess_fator = di_dol_fator / corp_fator

        rentab_table = {
            "Periodo": {
                "USD": self.fator2return(usd_fator),
                "DI": self.fator2return(di_fator),
                "DI USD": self.fator2return(di_dol_fator),
                "US Corp. I.G. Index": self.fator2return(corp_fator),
                "Excendente DI USD": self.fator2return(excess_fator),
            },
            "Anual": {
                "USD": self.get_anual(usd_fator),
                "DI": self.get_anual(di_fator),
                "DI USD": self.get_anual(di_dol_fator),
                "US Corp. I.G. Index": self.get_anual(corp_fator),
                "Excendente DI USD": self.get_anual(excess_fator),
            },
        }

        return rentab_table


class DiDolFig:
    def __init__(self, fator_df) -> None:
        self.fator_df = fator_df
        self.fator_df["di_usd"] = self.fator_df.di / self.fator_df.usd
        self.fator_df = self.fator_df / self.fator_df.iloc[0]

        self.xlabel_default = "Data"
        self.ylabel_default = "Acumulado equivalente ao ano em %"

    def create_fig(
        self, title: str, ylabel: str, xlabel: str, prices: dict[str, pd.Series]
    ):
        fig = go.Figure()

        for label, ser in prices.items():
            fig.add_trace(go.Scatter(x=ser.index, y=ser, mode="lines", name=label))

        fig.update_layout(
            title=title,
            xaxis_title=xlabel,
            yaxis_title=ylabel,
            showlegend=True,
            template="plotly_white",
            autosize=True,
        )

        fig.update_xaxes(showgrid=True, gridcolor="gray", gridwidth=0.5)
        fig.update_yaxes(showgrid=True, gridcolor="gray", gridwidth=0.5)

        fig.add_hline(y=0)

        ymin = min(price.min() for price in prices.values()) - 1

        fig.add_shape(
            type="rect",
            x0=min(price.index.min() for price in prices.values()),
            x1=max(price.index.max() for price in prices.values()),
            y0=ymin - -1,
            y1=0,
            fillcolor="lightcoral",
            opacity=0.3,
            line=dict(width=0),
        )
        return fig

    def prepare_price(
        self, serie: pd.Series, anualiza: AnualizaTipos, dias: int | None = None
    ):
        ser_chart = serie / serie.iloc[0]
        if anualiza == "fixo":
            assert isinstance(dias, int)
            ser_chart = ser_chart ** (252 / dias)
        elif anualiza == "posicao":
            ser_dias = pd.Series(range(1, len(serie) + 1))
            ser_dias.index = serie.index
            ser_chart = ser_chart ** (252 / ser_dias)

        ser_chart = (ser_chart - 1) * 100
        return ser_chart

    def prep(self, serie: pd.Series):
        ser = serie
        ser.name = "valor"
        df = pd.DataFrame(serie)
        df["dias"] = range(1, len(serie) + 1)
        df_qe = df.resample("QE").last()
        df_qe["valor"] = df_qe.valor / df_qe.valor.iloc[0]
        ser_qe_anual = df_qe.valor ** (252 / df_qe.dias)
        ser_chart = (ser_qe_anual - 1) * 100
        return ser_chart

    @cached_property
    def di_usd(self):
        title = "Comparando Retorno do USD com DI"
        usd = self.prep(self.fator_df.usd)
        di = self.prep(self.fator_df.di)

        prices = {
            "Taxa de Cambio BRL/USD": usd,
            "DI em BRL": di,
        }

        fig = self.create_fig(title, self.ylabel_default, self.xlabel_default, prices)
        return fig

    @cached_property
    def di_usd_corp(self):
        title = "Comparando Retorno do DI em USD com US Corp IG Index"
        di_usd = self.prep(self.fator_df.di_usd)
        corp = self.prep(self.fator_df.corp)

        prices = {"DI em USD": di_usd, "US Corp IG Index": corp}

        fig = self.create_fig(title, self.ylabel_default, self.xlabel_default, prices)
        return fig

    @cached_property
    def di_usd_excesso(self):
        title = "Retorno Adicional do DI em USD com US Corp IG Index"
        di_usd_corp = self.fator_df.di_usd / self.fator_df.corp
        di_usd_corp = self.prep(di_usd_corp)

        prices = {"DI em USD acima do US Corp IG Index": di_usd_corp}

        fig = self.create_fig(title, self.ylabel_default, self.xlabel_default, prices)
        return fig

    def excesso_years(self, years: int):
        title = f"Retorno Adicional Anualizado do DI em USD com US Corp IG Index, ultimos {years} anos"
        di_usd_corp = self.fator_df.di_usd / self.fator_df.corp
        di_usd_corp = di_usd_corp / di_usd_corp.iloc[0]

        shift_days = years * 252
        ser = di_usd_corp / di_usd_corp.shift(shift_days)
        ser = ser.dropna()
        ser = self.prepare_price(ser, "fixo", dias=years * 252)

        prices = {"DI em USD acima do US Corp IG Index": ser}
        fig = self.create_fig(title, self.ylabel_default, self.xlabel_default, prices)
        return fig
