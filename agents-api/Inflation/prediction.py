import pandas as pd
import warnings
import os
warnings.filterwarnings("ignore")

def load_and_clean_data(file_path, data_type='yoy'):
    try:
        df = pd.read_excel(file_path, sheet_name='Inflation Rates', skiprows=1, usecols='A:E')
    except:
        df = pd.read_excel(file_path, skiprows=1, usecols='A:E')

    df = df.dropna(how='all')
    suffix = '_yy' if data_type == 'yoy' else '_mm'
    df.columns = ['Date', f'Headline{suffix}', f'Core{suffix}',
                  f'Regulated{suffix}', f'Fruits_Veg{suffix}']

    df['Date'] = pd.to_datetime(df['Date'], format='%b %Y', errors='coerce')
    df = df.dropna(subset=['Date']).sort_values('Date').set_index('Date')

    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].str.rstrip('%').astype(float) / 100

    return df

# ---- LOAD RAW DATA ----
DATA_DIR = 'agents/Inflation/'
FILE_YY = os.path.join(DATA_DIR, 'Inflations Historical (7).xlsx')
FILE_MM = os.path.join(DATA_DIR, 'Inflations Historical (6).xlsx')
df_yy = load_and_clean_data(FILE_YY, "yoy")
df_mm = load_and_clean_data(FILE_MM, "mom")

df_combined = df_yy.join(df_mm, how="outer").ffill()

print("df_combined loaded:", df_combined.shape)




import numpy as np

def predict_lstm_next_n_months(
    df_raw,
    model,
    scaler_X,
    scaler_y,
    metadata,
    n_months
):
    target_col = metadata["target_col"]
    features = metadata["features"]
    window_size = metadata["window_size"]

    # ---- build lags ----
    df = df_raw.copy()
    df["lag_1"]  = df[target_col].shift(1)
    df["lag_3"]  = df[target_col].shift(3)
    df["lag_6"]  = df[target_col].shift(6)
    df["lag_12"] = df[target_col].shift(12)
    df = df.dropna()

    history = df[[target_col] + features].values
    X_hist = scaler_X.transform(history[:, 1:])

    preds_scaled = []

    for _ in range(n_months):
        x_input = X_hist[-window_size:].reshape(
            1, window_size, X_hist.shape[1]
        )

        pred = model.predict(x_input, verbose=0)[0,0]
        preds_scaled.append(pred)

        new_row = np.roll(X_hist[-1], 1)
        new_row[0] = pred
        X_hist = np.vstack([X_hist, new_row])

    preds = scaler_y.inverse_transform(
        np.array(preds_scaled).reshape(-1,1)
    ).flatten()

    return preds



from statsmodels.tsa.statespace.sarimax import SARIMAXResults
import joblib

def load_sarimax_artifacts(model_dir="."):
    sarimax_model = SARIMAXResults.load(
        f"{model_dir}/sarimax_mm_model.pkl"
    )
    metadata = joblib.load(
        f"{model_dir}/sarimax_metadata.pkl"
    )
    return sarimax_model, metadata

import numpy as np

def predict_sarimax_next_n_months(
    df_raw,
    sarimax_model,
    metadata,
    n_months
):
    yoy_col = metadata["yoy_col"]
    mom_col = metadata["mom_col"]

    preds_mm = sarimax_model.forecast(steps=n_months)

    previous_yoy = df_raw[yoy_col].iloc[-1]
    yoy_forecasts = []

    for i in range(n_months):
        old_mm = df_raw[mom_col].iloc[-12 + i]
        new_yoy = previous_yoy + preds_mm[i] - old_mm
        yoy_forecasts.append(new_yoy)
        previous_yoy = new_yoy

    return np.array(yoy_forecasts)



def load_all_models(model_dir="."):
    # ---- LSTM ----
    from tensorflow.keras.models import load_model
    import joblib

    lstm_model = load_model(f"{model_dir}/lstm_inflation_model.keras")
    scaler_X = joblib.load(f"{model_dir}/scaler_X.pkl")
    scaler_y = joblib.load(f"{model_dir}/scaler_y.pkl")
    lstm_meta = joblib.load(f"{model_dir}/lstm_metadata.pkl")

    # ---- SARIMAX ----
    sarimax_model, sarimax_meta = load_sarimax_artifacts(model_dir)

    return {
        "lstm": {
            "model": lstm_model,
            "scaler_X": scaler_X,
            "scaler_y": scaler_y,
            "meta": lstm_meta
        },
        "sarimax": {
            "model": sarimax_model,
            "meta": sarimax_meta
        }
    }


models = load_all_models()
print(" Models loaded")



def forecast_next_n_months(
    model_type,
    df_raw,
    models,
    n_months
):
    if model_type == "lstm":
        return predict_lstm_next_n_months(
            df_raw=df_raw,
            model=models["lstm"]["model"],
            scaler_X=models["lstm"]["scaler_X"],
            scaler_y=models["lstm"]["scaler_y"],
            metadata=models["lstm"]["meta"],
            n_months=n_months
        )

    elif model_type == "sarimax":
        return predict_sarimax_next_n_months(
            df_raw=df_raw,
            sarimax_model=models["sarimax"]["model"],
            metadata=models["sarimax"]["meta"],
            n_months=n_months
        )

    else:
        raise ValueError("model_type must be 'lstm' or 'sarimax'")



models = load_all_models()

lstm_6m = forecast_next_n_months(
    model_type="lstm",
    df_raw=df_combined,
    models=models,
    n_months=6
)

sarimax_6m = forecast_next_n_months(
    model_type="sarimax",
    df_raw=df_combined,
    models=models,
    n_months=6
)

print("LSTM next 6 months:", lstm_6m)
print("SARIMAX next 6 months:", sarimax_6m)

