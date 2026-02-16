import os 
import pandas as pd 
import databento as db 

def import_data(paths: list[str]) -> list[pd.DataFrame]:
    """Function used to load in databases from directory"""
    data = []
    for path in paths:
        if os.path.exists(path):
            data.append(
                db.DBNStore.from_file(path = path).to_df().dropna()
            )
        else:
            raise FileNotFoundError(f'No such file or directory {path}')
    return data 