# Loan Eligibility Prediction

A small machine learning app that predicts loan approval using a logistic regression model and a Streamlit user interface.

## Project Overview

- `train_model.py`: prepares the loan dataset, trains a logistic regression model, evaluates performance, and saves the model (`loan_model.pkl`) and scaler (`scaler.pkl`).
- `app.py`: launches a Streamlit app to collect applicant details, scale feature values, and predict loan approval.
- `loan_train_data.csv`: training dataset used to train the model.
- `loan_test_data.csv`: test dataset for validation or additional analysis.
- `loan_model.pkl`: trained model artifact loaded by the Streamlit app.
- `scaler.pkl`: scaler artifact used to normalize input features before prediction.
- `commands.md`: contains the Streamlit launch command for the app.

## Requirements

Recommended Python version: `3.8+`

Install dependencies:

```bash
python -m pip install pandas numpy scikit-learn streamlit
```

If you use a virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install pandas numpy scikit-learn streamlit
```

## Running the Model Training

If `loan_model.pkl` or `scaler.pkl` are missing or you want to retrain the model:

```bash
python train_model.py
```

This will:

1. load `loan_train_data.csv`
2. clean missing values
3. encode categorical features
4. scale numeric features
5. train a logistic regression model
6. save `loan_model.pkl` and `scaler.pkl`

## Launching the Streamlit App

Use the command from `commands.md`:

```bash
streamlit run app.py
```

Then open the local URL shown by Streamlit in your browser.

## App Inputs

The Streamlit interface asks for:

- Gender
- Married status
- Education level
- Applicant income
- Co-applicant income
- Loan amount
- Credit history

The app encodes these features, scales them, and returns one of:

- `Loan Approved!`
- `Loan Application Rejected.`

## Notes

- `app.py` expects `loan_model.pkl` and `scaler.pkl` to exist.
- If those artifacts are not present, run `train_model.py` first.
- The dataset files are provided for training and testing, but the app only uses the pre-trained model and scaler.

## Contact

Use this repository as a starting point for loan eligibility modeling and UI demonstration with Streamlit.
