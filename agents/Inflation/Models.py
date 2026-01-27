import os
import random
import numpy as np
import tensorflow as tf

# Force deterministic operations where possible (some ops are still non-deterministic on GPU)
os.environ["TF_DETERMINISTIC_OPS"] = "1"

SEED = 42

random.seed(SEED)
np.random.seed(SEED)
tf.random.set_seed(SEED)



import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import matplotlib.pyplot as plt
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from scipy.stats import norm
import warnings
warnings.filterwarnings('ignore')

# ==================== DATA LOADING ====================

def load_and_clean_data(file_path, data_type='yoy'):
    """Load and clean inflation data"""
    
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

# Update the path to include the subfolders
DATA_DIR = 'agents/Inflation/'
FILE_YY = os.path.join(DATA_DIR, 'Inflations Historical (7).xlsx')
FILE_MM = os.path.join(DATA_DIR, 'Inflations Historical (6).xlsx')
df_yy = load_and_clean_data(FILE_YY, 'yoy')
df_mm = load_and_clean_data(FILE_MM, 'mom')
df_combined = df_yy.join(df_mm, how='outer').fillna(method='ffill')

print(f"Dataset: {len(df_combined)} months from {df_combined.index[0]} to {df_combined.index[-1]}")




import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error

class TimeSeriesEvaluationPipeline:
    def __init__(self, horizon=12):
        self.horizon = horizon

    def train_test_split(self, series):
        train = series[:-self.horizon]
        test = series[-self.horizon:]
        return train, test

    def naive_forecast(self, train):
        return np.repeat(train[-1], self.horizon)

    def evaluate(self, y_true, y_pred):
        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))

        direction = np.sign(np.diff(y_true)) == np.sign(np.diff(y_pred))
        directional_accuracy = direction.mean()

        return {
            "MAE": mae,
            "RMSE": rmse,
            "Directional_Accuracy": directional_accuracy
        }




from statsmodels.tsa.arima.model import ARIMA

pipeline = TimeSeriesEvaluationPipeline(horizon=12)

train, test = pipeline.train_test_split(df_combined["Headline_yy"].values)

# Train ARIMA
model = ARIMA(train, order=(1,1,1))
model_fit = model.fit()

# Forecast
preds = model_fit.forecast(steps=12)

# Evaluate
results = pipeline.evaluate(test, preds)
baseline = pipeline.evaluate(test, pipeline.naive_forecast(train))

print("ARIMA:", results)
print("Naive:", baseline)



df = df_combined.copy()
target = "Headline_yy"

df["lag_1"]  = df[target].shift(1)
df["lag_3"]  = df[target].shift(3)
df["lag_6"]  = df[target].shift(6)
df["lag_12"] = df[target].shift(12)

df = df.dropna()



features = ["lag_1", "lag_3", "lag_6", "lag_12"]

data = df[[target] + features].values

pipeline = TimeSeriesEvaluationPipeline(horizon=12)
train, test = pipeline.train_test_split(data)

y_train = train[:, 0]
X_train = train[:, 1:]

y_test = test[:, 0]



scaler_X = StandardScaler()
scaler_y = StandardScaler()

X_train_scaled = scaler_X.fit_transform(X_train)
y_train_scaled = scaler_y.fit_transform(y_train.reshape(-1,1)).flatten()



def create_multivariate_sequences(X, y, window):
    Xs, ys = [], []
    for i in range(len(X) - window):
        Xs.append(X[i:i+window])
        ys.append(y[i+window])
    return np.array(Xs), np.array(ys)

window_size = 12
X_seq, y_seq = create_multivariate_sequences(
    X_train_scaled, y_train_scaled, window_size
)




from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

# Model definition — with seeds already set above, this is now reproducible
model = Sequential([
    LSTM(32, input_shape=(window_size, X_seq.shape[2]),
         kernel_initializer='glorot_uniform',   # default, but explicit is good
         recurrent_initializer='orthogonal'),
    Dense(1)
])

model.compile(optimizer="adam", loss="mse")

# Fit — epochs=60 is fine; batch_size default (32) is ok
# shuffle=True is default → but with seeds it's reproducible
model.fit(X_seq, y_seq, epochs=60, verbose=0, shuffle=True)


history_X = X_train_scaled.copy()
history_y = y_train_scaled.copy()

preds_scaled = []

for _ in range(12):
    x_input = history_X[-window_size:].reshape(
        1, window_size, history_X.shape[1]
    )
    pred = model.predict(x_input, verbose=0)[0,0]
    preds_scaled.append(pred)

    new_row = np.roll(history_X[-1], 1)
    new_row[0] = pred
    history_X = np.vstack([history_X, new_row])

lstm_preds = scaler_y.inverse_transform(
    np.array(preds_scaled).reshape(-1,1)
).flatten()




print("LSTM (with lags):", pipeline.evaluate(y_test, lstm_preds))
print("Naive:", pipeline.evaluate(y_test, pipeline.naive_forecast(y_train)))


from statsmodels.tsa.statespace.sarimax import SARIMAX

train_mm, test_mm = pipeline.train_test_split(df_combined["Headline_mm"].values)

sar_model_mm = SARIMAX(train_mm, order=(1,0,1), seasonal_order=(1,0,1,12))
sar_fit_mm = sar_model_mm.fit(disp=False)
preds_mm = sar_fit_mm.forecast(steps=12)

# Derive YY (approx formula to handle ups without compounding error)
yoy_forecast = []
previous_yoy = train[-1]
for i in range(12):
    old_mm = df_combined['Headline_mm'].values[len(train) -12 + i]
    new_yoy = previous_yoy + preds_mm[i] - old_mm
    yoy_forecast.append(new_yoy)
    previous_yoy = new_yoy
yoy_forecast = np.array(yoy_forecast)

mm_results = pipeline.evaluate(test, yoy_forecast)
print("SARIMAX on MM, derive YY:", mm_results)


import joblib

# ---- save model ----
model.save("lstm_inflation_model.keras")

# ---- save scalers ----
joblib.dump(scaler_X, "scaler_X.pkl")
joblib.dump(scaler_y, "scaler_y.pkl")

# ---- save metadata ----
metadata = {
    "target_col": "Headline_yy",
    "features": ["lag_1", "lag_3", "lag_6", "lag_12"],
    "window_size": 12
}

joblib.dump(metadata, "lstm_metadata.pkl")

print("✅ Model, scalers, and metadata saved")




sar_model_full = SARIMAX(
    df_combined["Headline_mm"].values,
    order=(1,0,1),
    seasonal_order=(1,0,1,12)
)

sar_fit_full = sar_model_full.fit(disp=False)
sar_fit_full.save("sarimax_mm_model.pkl")

# Save SARIMAX metadata
import joblib

sarimax_metadata = {
    "yoy_col": "Headline_yy",
    "mom_col": "Headline_mm",
    "seasonal_period": 12
}

joblib.dump(sarimax_metadata, "sarimax_metadata.pkl")

print("✅ SARIMAX model and metadata saved")





