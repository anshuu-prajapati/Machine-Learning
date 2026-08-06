import pandas as pd
import numpy as np
import pickle
import streamlit as st

# Load artifacts
with open('loan_model.pkl', 'rb') as f:
    model = pickle.load(f)

with open('scaler.pkl', 'rb') as f:
    scaler = pickle.load(f)

st.title("🏦 Loan Eligibility Predictor")

# Form inputs
gender = st.selectbox("Gender", ["Male", "Female"])
married = st.selectbox("Married", ["No", "Yes"])
education = st.selectbox("Education", ["Graduate", "Not Graduate"])
applicant_income = st.number_input(
    "Applicant Income ($)", min_value=0, value=5000
)
coapplicant_income = st.number_input(
    "Co-applicant Income ($)", min_value=0, value=0
)
loan_amount = st.number_input(
    "Loan Amount (in Thousands)", min_value=0, value=150
)
credit_history = st.selectbox(
    "Credit History Clear?", ["Yes (1.0)", "No (0.0)"]
)

if st.button("Check Eligibility"):
    # Encode inputs
    gender_enc = 1 if gender == "Male" else 0
    married_enc = 1 if married == "Yes" else 0
    education_enc = 0 if education == "Graduate" else 1
    credit_enc = 1.0 if "Yes" in credit_history else 0.0

    # Create DataFrame with matching feature column names
    input_df = pd.DataFrame(
        [[
            gender_enc,
            married_enc,
            education_enc,
            applicant_income,
            coapplicant_income,
            loan_amount,
            credit_enc,
        ]],
        columns=[
            'Gender',
            'Married',
            'Education',
            'ApplicantIncome',
            'CoapplicantIncome',
            'LoanAmount',
            'Credit_History',
        ],
    )

    # Scale inputs & predict
    scaled_features = scaler.transform(input_df)
    prediction = model.predict(scaled_features)

    if prediction[0] == 1:
        st.success("🎉 Loan Approved!")
    else:
        st.error("❌ Loan Application Rejected.")