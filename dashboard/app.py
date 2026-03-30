import streamlit as st
import requests

st.title("Coffee Vision Dashboard")

uploaded = st.file_uploader("Upload video")

if uploaded:
    files = {"file": uploaded}
    requests.post("http://localhost:8000/upload", files=files)

st.header("KPIs")

st.metric("Customers", 10)
st.metric("Avg Wait", "3 min")