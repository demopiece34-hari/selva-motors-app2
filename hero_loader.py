from __future__ import annotations
import streamlit as st

def show_loader(message="Loading...", wait_text="Please wait"):
    st.markdown(f"""
    <div style="position:fixed;inset:0;z-index:999999;background:rgba(255,255,255,.98);display:flex;align-items:center;justify-content:center;">
      <div style="text-align:center;padding:28px 30px;border:2px solid #fecaca;border-radius:28px;box-shadow:0 30px 90px rgba(127,29,29,.22);background:#fff;">
        <div style="color:#e31837;font-size:54px;font-weight:1000;letter-spacing:2px;">HERO</div>
        <div style="width:68px;height:68px;border-radius:50%;border:7px solid #fee2e2;border-top-color:#e31837;margin:16px auto;animation:spin 0.8s linear infinite;"></div>
        <div style="font-size:20px;font-weight:900;color:#111827;">{message}</div>
        <div style="font-size:14px;color:#4b5563;margin-top:8px;">{wait_text}</div>
      </div>
    </div>
    <style>@keyframes spin{{to{{transform:rotate(360deg)}}}}</style>
    """, unsafe_allow_html=True)
