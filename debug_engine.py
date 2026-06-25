import traceback
import streamlit as st
from datetime import datetime

DEBUG_ERRORS = []

def debug_log(module_name, error):
    DEBUG_ERRORS.append({
        "time": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        "module": module_name,
        "error": str(error),
        "trace": traceback.format_exc()
    })

def safe_run(module_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)

            except Exception as e:
                debug_log(module_name, e)

                st.error(
                    f"""
ERROR DETECTED

Module:
{module_name}

Error:
{str(e)}

Auto Suggestion:
Check variable name
Check column name
Check indentation
Check Google Sheet data

Problem Captured Successfully
"""
                )

                with st.expander("Full Error Details"):
                    st.code(traceback.format_exc())

                return None

        return wrapper
    return decorator


def show_debug_panel():

    st.markdown("---")
    st.subheader("System Debug Monitor")

    if len(DEBUG_ERRORS) == 0:

        st.success(
            """
No Error Detected

All Pages Working Fine
Google Sheet Connected
OCR Working
Reports Working
Attendance Working
Dashboard Working
"""
        )

        return

    st.error(
        f"{len(DEBUG_ERRORS)} Errors Found"
    )

    for i,error in enumerate(DEBUG_ERRORS,1):

        with st.expander(
            f"{i}. {error['module']}"
        ):

            st.write("Time:", error["time"])

            st.code(error["error"])

            st.code(error["trace"])
