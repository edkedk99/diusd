from diusd.web import di
from dotenv import load_dotenv
import os
import sys

if __name__ == "__main__":
    load_dotenv(".env")

    file_path = os.getenv("DIUSD_FILE_PATH")
    if not file_path:
        err = "Falta env DIUSD_FILE_PATH"
        raise ValueError(err)

    years = 20
    if len(sys.argv) > 1:
        years = int(sys.argv[1])

    di_dol_data = di.DiDolData(file_path, 20)

    qtde = di_dol_data.df.shape[0]
    first_date = di_dol_data.df.iloc[0].name
    last_date = di_dol_data.df.iloc[-1].name
    output = f"Salvo {qtde} datas, de {first_date} ate {last_date}"
