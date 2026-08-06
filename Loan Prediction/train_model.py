import pandas as pd
import numpy as np
import pickle

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

# ---------------------------------------------------------
# 1. Load Data
# ---------------------------------------------------------
df = pd.read_csv('loan_train_data.csv')

print("--- Data Preview ---")
print(df.head())
print("\n--- Missing Values Before Cleaning ---")
print(df.isnull().sum())

# ---------------------------------------------------------
# 2. Preprocessing & Data Cleaning (Fixed Copy-on-Write)
# ---------------------------------------------------------
# Fill missing numerical values with median
if 'LoanAmount' in df.columns:
    df['LoanAmount'] = df['LoanAmount'].fillna(df['LoanAmount'].median())

if 'Credit_History' in df.columns:
    df['Credit_History'] = df['Credit_History'].fillna(df['Credit_History'].mode()[0])

# Fill missing categorical values with mode across all relevant feature columns
categorical_to_fill = ['Gender', 'Married', 'Dependents', 'Education', 'Self_Employed']
for col in categorical_to_fill:
    if col in df.columns:
        df[col] = df[col].fillna(df[col].mode()[0])

# Encode categorical variables to numerical format
label_encoders = {}
categorical_cols = ['Gender', 'Married', 'Education', 'Self_Employed', 'Loan_Status']

for col in categorical_cols:
    if col in df.columns:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col])
        label_encoders[col] = le

# Verify no NaNs remain
print("\n--- Missing Values After Cleaning ---")
print(df.isnull().sum())

# ---------------------------------------------------------
# 3. Feature Selection & Train-Test Split
# ---------------------------------------------------------
feature_cols = ['Gender', 'Married', 'Education', 'ApplicantIncome', 
                'CoapplicantIncome', 'LoanAmount', 'Credit_History']

X = df[feature_cols]
y = df['Loan_Status']  # Target: 1 = Approved (Y), 0 = Rejected (N)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ---------------------------------------------------------
# 4. Feature Scaling
# ---------------------------------------------------------
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# ---------------------------------------------------------
# 5. Model Training
# ---------------------------------------------------------
model = LogisticRegression()
model.fit(X_train_scaled, y_train)

# ---------------------------------------------------------
# 6. Evaluation
# ---------------------------------------------------------
y_pred = model.predict(X_test_scaled)
acc = accuracy_score(y_test, y_pred)

print(f"\nModel Accuracy: {acc * 100:.2f}%")
print("\nClassification Report:\n", classification_report(y_test, y_pred))

# ---------------------------------------------------------
# 7. Save Artifacts with Pickle
# ---------------------------------------------------------
with open('loan_model.pkl', 'wb') as model_file:
    pickle.dump(model, model_file)

with open('scaler.pkl', 'wb') as scaler_file:
    pickle.dump(scaler, scaler_file)

print("\nSaved 'loan_model.pkl' and 'scaler.pkl' successfully.")