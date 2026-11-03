"""
Letter Pad Module for SELVA MOTORS
Feature: Direct browser print on official Selva Motors letterhead without downloading.
"""

import os
import base64
import html
import streamlit as st
import streamlit.components.v1 as components

# Path to the letterhead template
LETTERHEAD_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "assets", "selva_letterpad_bg.png")

def get_image_base64(image_path: str) -> str:
    """Reads and encodes the letterhead background to base64."""
    if not os.path.exists(image_path):
        return ""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def build_letter_html(date_str, ref_no, recipient_name, recipient_addr, subject, body, sign_name, sign_title, bg_base64=""):
    """
    Constructs the exact A4 layout with letterhead background.
    Safe HTML escaping is applied to all user-entered inputs.
    """
    safe_date = html.escape(date_str or "")
    safe_ref = html.escape(ref_no or "")
    safe_rec_name = html.escape(recipient_name or "")
    safe_rec_addr = "<br>".join([html.escape(line) for line in (recipient_addr or "").splitlines() if line.strip()])
    safe_sub = html.escape(subject or "")
    safe_body = "".join([f"<p>{html.escape(p)}</p>" for p in (body or "").split("\n\n") if p.strip()])
    safe_sign_name = html.escape(sign_name or "")
    safe_sign_title = html.escape(sign_title or "Authorised Signatory")

    bg_style = ""
    if bg_base64:
        bg_style = f"background-image: url('data:image/png;base64,{bg_base64}');"

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4 portrait;
                margin: 0;
            }}
            * {{
                box-sizing: border-box;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                color-adjust: exact !important;
            }}
            body, html {{
                margin: 0;
                padding: 0;
                background-color: #fff;
                font-family: 'Segoe UI', Arial, Helvetica, sans-serif;
                color: #111;
            }}
            .a4-sheet {{
                width: 210mm;
                min-height: 297mm;
                height: 297mm;
                margin: 0 auto;
                position: relative;
                background-repeat: no-repeat;
                background-position: center top;
                background-size: 210mm 297mm;
                {bg_style}
                overflow: hidden;
            }}
            /* Content printable zone: clears 46mm header and 35mm footer */
            .letter-content-container {{
                position: absolute;
                top: 48mm;
                bottom: 36mm;
                left: 22mm;
                right: 22mm;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                font-size: 11pt;
                line-height: 1.5;
            }}
            .meta-section {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 12px;
                font-weight: 500;
            }}
            .recipient-section {{
                margin-bottom: 14px;
            }}
            .recipient-title {{
                font-weight: bold;
                margin-bottom: 2px;
            }}
            .subject-line {{
                font-weight: bold;
                text-decoration: underline;
                margin-bottom: 14px;
            }}
            .letter-body {{
                text-align: justify;
                flex-grow: 1;
            }}
            .letter-body p {{
                margin-top: 0;
                margin-bottom: 10px;
                text-indent: 18px;
            }}
            .signature-section {{
                width: 220px;
                align-self: flex-end;
                text-align: right;
                margin-top: 15px;
            }}
            .sig-space {{
                height: 48px;
            }}
            .sig-name {{
                font-weight: bold;
                border-top: 1px dashed #666;
                padding-top: 4px;
            }}
            .sig-title {{
                font-size: 9.5pt;
                color: #333;
            }}
        </style>
    </head>
    <body>
        <div class="a4-sheet">
            <div class="letter-content-container">
                <div>
                    <div class="meta-section">
                        <div>{"<b>Ref No:</b> " + safe_ref if safe_ref else ""}</div>
                        <div>{"<b>Date:</b> " + safe_date if safe_date else ""}</div>
                    </div>

                    <div class="recipient-section">
                        <div class="recipient-title">To,</div>
                        {f"<b>{safe_rec_name}</b><br>" if safe_rec_name else ""}
                        <div>{safe_rec_addr}</div>
                    </div>

                    {f'<div class="subject-line">Sub: {safe_sub}</div>' if safe_sub else ''}

                    <div class="letter-body">
                        {safe_body}
                    </div>
                </div>

                <div class="signature-section">
                    <div>For <b>SELVA MOTORS</b></div>
                    <div class="sig-space"></div>
                    <div class="sig-name">{safe_sign_name}</div>
                    <div class="sig-title">{safe_sign_title}</div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

def render_letter_pad_page():
    st.title("🖨️ SELVA MOTORS — Official Letter Pad")

    # Verify background image existence
    bg_base64 = get_image_base64(LETTERHEAD_IMAGE_PATH)
    if not bg_base64:
        st.warning(
            f"Letterhead image not found at `{LETTERHEAD_IMAGE_PATH}`. "
            "Please ensure `selva_letterpad_bg.png` is placed inside the `assets/` directory."
        )

    # Initialize isolated session states
    defaults = {
        "lp_date": "2026-11-03",
        "lp_ref_no": "SM/KVR/2026-27/",
        "lp_recipient_name": "",
        "lp_recipient_addr": "",
        "lp_subject": "",
        "lp_body": "",
        "lp_sign_name": "Authorised Representative",
        "lp_sign_title": "SELVA MOTORS, Kilvelur",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    col_form, col_preview = st.columns([1, 1], gap="large")

    with col_form:
        st.subheader("📝 Letter Details")
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1:
            st.session_state.lp_date = st.text_input("Letter Date", value=st.session_state.lp_date)
        with r1_c2:
            st.session_state.lp_ref_no = st.text_input("Reference No. (Optional)", value=st.session_state.lp_ref_no)

        st.session_state.lp_recipient_name = st.text_input(
            "Recipient / Organization Name", 
            value=st.session_state.lp_recipient_name,
            placeholder="e.g. The Regional Transport Officer"
        )
        st.session_state.lp_recipient_addr = st.text_area(
            "Recipient Address", 
            value=st.session_state.lp_recipient_addr,
            rows=3,
            placeholder="Nagapattinam / Thiruvarur"
        )
        st.session_state.lp_subject = st.text_input(
            "Subject", 
            value=st.session_state.lp_subject,
            placeholder="e.g. Vehicle Registration / RC Book Dispatch"
        )
        st.session_state.lp_body = st.text_area(
            "Letter Message / Body", 
            value=st.session_state.lp_body,
            rows=10,
            placeholder="Type your official communication here..."
        )

        r2_c1, r2_c2 = st.columns(2)
        with r2_c1:
            st.session_state.lp_sign_name = st.text_input("Signatory Name", value=st.session_state.lp_sign_name)
        with r2_c2:
            st.session_state.lp_sign_title = st.text_input("Signatory Title", value=st.session_state.lp_sign_title)

        st.markdown("---")
        
        # Action button triggering direct print
        trigger_print = st.button("🖨️ PRINT LETTER", type="primary", use_container_width=True)

    # Generate document markup
    letter_html = build_letter_html(
        date_str=st.session_state.lp_date,
        ref_no=st.session_state.lp_ref_no,
        recipient_name=st.session_state.lp_recipient_name,
        recipient_addr=st.session_state.lp_recipient_addr,
        subject=st.session_state.lp_subject,
        body=st.session_state.lp_body,
        sign_name=st.session_state.lp_sign_name,
        sign_title=st.session_state.lp_sign_title,
        bg_base64=bg_base64
    )

    with col_preview:
        st.subheader("👁️ Live A4 Preview")
        # Scaled down to comfortably fit Streamlit column width while maintaining 1:1.414 aspect ratio
        preview_wrapper = f"""
        <div style="border: 1px solid #ddd; box-shadow: 0 4px 10px rgba(0,0,0,0.15); border-radius: 4px; overflow: hidden; height: 750px; background: #e8e8e8; display: flex; justify-content: center; align-items: flex-start; padding: 15px 0;">
            <iframe srcdoc="{html.escape(letter_html)}" style="width: 210mm; height: 297mm; transform: scale(0.68); transform-origin: top center; border: none; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.25);"></iframe>
        </div>
        """
        st.markdown(preview_wrapper, unsafe_allow_html=True)

    # DIRECT PRINT EXECUTION (No download, opens native print dialog)
    if trigger_print:
        # Encodes full HTML to trigger browser window print dialog
        encoded_html = base64.b64encode(letter_html.encode("utf-8")).decode("utf-8")
        print_component = f"""
        <script>
            (function() {{
                const iframe = document.createElement('iframe');
                iframe.style.position = 'fixed';
                iframe.style.right = '0';
                iframe.style.bottom = '0';
                iframe.style.width = '0';
                iframe.style.height = '0';
                iframe.style.border = '0';
                document.body.appendChild(iframe);

                const rawContent = atob("{encoded_html}");
                iframe.contentWindow.document.open();
                iframe.contentWindow.document.write(rawContent);
                iframe.contentWindow.document.close();

                iframe.contentWindow.focus();
                setTimeout(() => {{
                    iframe.contentWindow.print();
                    setTimeout(() => {{
                        document.body.removeChild(iframe);
                    }}, 2000);
                }}, 350);
            }})();
        </script>
        """
        components.html(print_component, height=0, width=0)
        st.toast("Opening print dialog...", icon="🖨️")
