import streamlit as st
import requests
import json
from datetime import datetime
import time

# Page Configuration
st.set_page_config(
    page_title="Medical Document Intelligence Platform",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Professional CSS Styling - Dark Theme
st.markdown("""
    <style>
    /* Main background - Dark theme */
    .stApp {
        background-color: #0f172a;
    }

    /* Sidebar styling - Dark */
    [data-testid="stSidebar"] {
        background-color: #1e293b;
        border-right: 1px solid #334155;
    }

    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4 {
        color: #f1f5f9 !important;
    }

    /* Force all sidebar select boxes to have dark backgrounds */
    [data-testid="stSidebar"] [data-baseweb="select"],
    [data-testid="stSidebar"] .stSelectbox {
        background-color: #334155 !important;
    }

    [data-testid="stSidebar"] [data-baseweb="select"] *,
    [data-testid="stSidebar"] .stSelectbox * {
        color: #f1f5f9 !important;
        background-color: transparent !important;
    }

    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-baseweb="select"] div[role="button"] {
        background-color: #334155 !important;
        border: 1px solid #475569 !important;
    }

    /* Text styling - Light fonts for dark theme */
    .stMarkdown, .stText, p, span, div {
        color: #e2e8f0 !important;
        font-size: 15px !important;
        line-height: 1.6 !important;
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }

    /* Headers - Light colors for dark theme */
    h1 {
        color: #f1f5f9 !important;
        font-size: 36px !important;
        font-weight: 700 !important;
        margin-bottom: 8px !important;
        letter-spacing: -0.5px;
    }

    h2 {
        color: #e2e8f0 !important;
        font-size: 24px !important;
        font-weight: 600 !important;
        margin-top: 24px !important;
        margin-bottom: 12px !important;
    }

    h3 {
        color: #cbd5e1 !important;
        font-size: 18px !important;
        font-weight: 600 !important;
        margin-bottom: 8px !important;
    }

    /* File uploader - Dark theme */
    [data-testid="stFileUploader"] {
        background-color: #1e293b;
        border: 2px dashed #475569;
        border-radius: 8px;
        padding: 24px;
        transition: border-color 0.2s;
    }

    [data-testid="stFileUploader"]:hover {
        border-color: #60a5fa;
    }

    [data-testid="stFileUploader"] label,
    [data-testid="stFileUploader"] p,
    [data-testid="stFileUploader"] small,
    [data-testid="stFileUploader"] span {
        color: #cbd5e1 !important;
    }

    [data-testid="stFileUploader"] section {
        background-color: #334155 !important;
        border: 2px dashed #475569 !important;
    }

    [data-testid="stFileUploader"] section div,
    [data-testid="stFileUploader"] section span,
    [data-testid="stFileUploader"] section small {
        color: #94a3b8 !important;
    }

    /* Buttons - Bright blue for dark theme */
    .stButton > button {
        background-color: #3b82f6;
        color: white;
        font-size: 15px !important;
        font-weight: 600;
        padding: 10px 24px;
        border-radius: 6px;
        border: none;
        transition: all 0.2s;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }

    .stButton > button:hover {
        background-color: #60a5fa;
        box-shadow: 0 4px 6px rgba(0,0,0,0.4);
    }

    /* Status boxes - Dark theme styling */
    .stSuccess {
        background-color: #064e3b;
        color: #86efac !important;
        font-size: 14px !important;
        border-left: 4px solid #10b981;
        padding: 12px 16px;
        border-radius: 4px;
    }

    .stError {
        background-color: #7f1d1d;
        color: #fca5a5 !important;
        font-size: 14px !important;
        border-left: 4px solid #ef4444;
        padding: 12px 16px;
        border-radius: 4px;
    }

    .stWarning {
        background-color: #78350f;
        color: #fcd34d !important;
        font-size: 14px !important;
        border-left: 4px solid #f59e0b;
        padding: 12px 16px;
        border-radius: 4px;
    }

    .stInfo {
        background-color: #1e3a8a;
        color: #93c5fd !important;
        font-size: 14px !important;
        border-left: 4px solid #3b82f6;
        padding: 12px 16px;
        border-radius: 4px;
    }

    /* Metrics - Light colors for dark theme */
    [data-testid="stMetricValue"] {
        font-size: 28px !important;
        color: #f1f5f9 !important;
        font-weight: 700 !important;
    }

    [data-testid="stMetricLabel"] {
        font-size: 13px !important;
        color: #94a3b8 !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* JSON viewer - White text on dark background */
    .stJson {
        background-color: #1f2937 !important;
        border: 1px solid #374151;
        border-radius: 6px;
        padding: 16px;
        font-size: 13px !important;
    }

    .stJson, .stJson * {
        color: #f9fafb !important;
    }

    .stJson span {
        color: #f9fafb !important;
    }

    .stJson div {
        color: #f9fafb !important;
    }

    .stJson pre {
        background-color: #1f2937 !important;
        color: #f9fafb !important;
    }

    .stJson .json-key {
        color: #93c5fd !important;
    }

    .stJson .json-string {
        color: #86efac !important;
    }

    .stJson .json-number {
        color: #fbbf24 !important;
    }

    .stJson .json-boolean {
        color: #c084fc !important;
    }

    .stJson .json-null {
        color: #9ca3af !important;
    }

    /* Override any inline styles in JSON viewer */
    [data-testid="stJson"] {
        background-color: #1f2937 !important;
    }

    [data-testid="stJson"] * {
        color: #f9fafb !important;
    }


    /* Ensure expander content with dark backgrounds has white text */
    .streamlit-expanderContent pre,
    .streamlit-expanderContent code {
        background-color: #1f2937 !important;
        color: #f9fafb !important;
    }

    .streamlit-expanderContent .stJson {
        background-color: #1f2937 !important;
    }

    .streamlit-expanderContent .stJson * {
        color: #f9fafb !important;
    }

    /* Code blocks */
    code {
        background-color: #1f2937;
        color: #f9fafb !important;
        padding: 2px 6px;
        border-radius: 3px;
        font-size: 13px !important;
        font-family: 'Monaco', 'Menlo', monospace;
    }

    pre {
        background-color: #1f2937 !important;
        color: #f9fafb !important;
        padding: 12px;
        border-radius: 6px;
        border: 1px solid #374151;
    }

    pre code {
        color: #f9fafb !important;
        background-color: transparent !important;
    }

    pre * {
        color: #f9fafb !important;
    }

    /* Select box - Dark theme */
    [data-baseweb="select"] {
        background-color: #334155 !important;
    }

    [data-baseweb="select"] > div {
        background-color: #334155 !important;
    }

    [data-baseweb="select"] div,
    [data-baseweb="select"] span,
    [data-baseweb="select"] input {
        color: #f1f5f9 !important;
        background-color: #334155 !important;
    }

    /* Streamlit selectbox wrapper */
    .stSelectbox > div > div {
        background-color: #334155 !important;
    }

    .stSelectbox [data-baseweb="select"] div[role="button"] {
        background-color: #334155 !important;
        border: 1px solid #475569 !important;
    }

    .stSelectbox [data-baseweb="select"] div[role="button"] span,
    .stSelectbox [data-baseweb="select"] div[role="button"] div {
        color: #f1f5f9 !important;
    }

    /* Select dropdown menu */
    [data-baseweb="menu"] {
        background-color: #1e293b !important;
    }

    [data-baseweb="menu"] li {
        color: #e2e8f0 !important;
        background-color: #1e293b !important;
    }

    [data-baseweb="menu"] li:hover {
        background-color: #334155 !important;
    }

    /* Text input fields */
    .stTextInput input,
    .stSelectbox select,
    .stNumberInput input {
        color: #f1f5f9 !important;
        background-color: #334155 !important;
        border: 1px solid #475569 !important;
    }

    /* Tabs - Dark theme */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 2px solid #334155;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: #94a3b8;
        font-size: 14px !important;
        font-weight: 500;
        padding: 10px 20px;
        border-radius: 0;
        border-bottom: 2px solid transparent;
    }

    .stTabs [aria-selected="true"] {
        background-color: transparent;
        color: #60a5fa !important;
        border-bottom: 2px solid #60a5fa;
    }

    /* Spinner */
    .stSpinner > div {
        border-top-color: #60a5fa !important;
    }

    /* Dataframe - Dark theme table */
    .dataframe {
        font-size: 14px !important;
        color: #e2e8f0 !important;
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
    }
    
    /* Progress bar */
    .stProgress > div > div {
        background-color: #60a5fa;
    }

    /* Uploaded files list */
    [data-testid="stFileUploadDropzone"] {
        background-color: #334155 !important;
    }

    [data-testid="stFileUploadDropzone"] * {
        color: #cbd5e1 !important;
    }

    /* All labels should be visible */
    label {
        color: #cbd5e1 !important;
    }

    /* Radio and checkbox text */
    [data-testid="stRadio"] label,
    [data-testid="stCheckbox"] label {
        color: #e2e8f0 !important;
    }

    /* Expander - Dark theme */
    .streamlit-expanderHeader {
        background-color: #1e293b;
        color: #e2e8f0 !important;
        font-size: 15px !important;
        font-weight: 600;
        border-radius: 6px;
        border: 1px solid #334155;
    }

    .streamlit-expanderContent {
        background-color: #1e293b !important;
        padding: 16px;
    }
    </style>
""", unsafe_allow_html=True)

# API Configuration
API_URL = "http://localhost:8000/process"

# Header
st.markdown("""
<div style='padding: 20px 0; border-bottom: 2px solid #334155; margin-bottom: 24px;'>
    <h1 style='margin: 0; color: #f1f5f9; font-size: 32px; font-weight: 700;'>Medical Document Intelligence Platform</h1>
    <p style='margin: 8px 0 0 0; color: #94a3b8; font-size: 15px;'>AI-powered document processing with clinical validation and HIPAA-compliant redaction</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### Configuration")

    # API Status Check
    try:
        response = requests.get("http://localhost:8000/docs", timeout=2)
        if response.status_code == 200:
            st.success("API Server: Online")
        else:
            st.error("API Server: Offline")
    except:
        st.error("API Server: Not Running")
        st.info(
            "Start server: `python -m uvicorn api:api --host 127.0.0.1 --port 8000`")

    st.markdown("---")

    # LLM Provider Selection
    st.markdown("### LLM Provider")

    llm_provider = st.selectbox(
        "Select Provider",
        options=["Ollama", "Groq", "Bedrock"],
        index=0,  # Default to Ollama
        help="Choose which LLM provider to use for document processing"
    )

    # Load credentials from environment
    import os
    from dotenv import load_dotenv
    load_dotenv()

    # Provider-specific configuration display
    if llm_provider == "Groq":
        groq_api_key = os.getenv("GROQ_API_KEY", "")
        if groq_api_key:
            st.success("Groq API Key: Configured")
        else:
            st.warning("Groq API key not configured")
            st.info("Add GROQ_API_KEY to .env file")

    elif llm_provider == "Bedrock":
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        aws_region = os.getenv("AWS_REGION", "us-east-1")

        if aws_access_key and aws_secret_key:
            st.success("AWS Credentials: Configured")
        else:
            st.warning("AWS credentials not configured")
            st.info("Add credentials to .env file")

    else:  # Ollama
        st.info("Local Ollama instance: http://localhost:11434")

    st.markdown("---")

    # Processing options
    st.markdown("### ⚙️ Processing Options")

    # Human-in-the-loop feature (more prominent)
    st.markdown("#### 🧑‍⚕️ Human Review Mode")

    col_toggle, col_info = st.columns([1, 2])

    with col_toggle:
        enable_human_review = st.toggle(
            "Enable Human Review",
            value=False,
            help="Enable manual review and approval of AI-suggested repairs"
        )

    with col_info:
        if enable_human_review:
            st.success(
                "✅ **Human Review ENABLED** - You will review all repairs before they are applied")
        else:
            st.info(
                "ℹ️ **Auto-Repair Mode** - AI will automatically fix detected issues")

    # Expandable explanation
    with st.expander("ℹ️ What is Human Review?"):
        st.markdown("""
        **Human Review Mode** pauses processing when the AI detects and fixes issues, allowing you to:
        
        - 👀 **Review** AI-suggested corrections before they're applied
        - ✅ **Approve** corrections you agree with
        - ❌ **Reject** and keep original data
        - ✏️ **Override** with your own manual corrections
        
        **Common scenarios that trigger review:**
        - Invalid medication dosage units (e.g., "liters" instead of "mg")
        - Non-standard medical units
        - Suspicious data patterns
        
        **When to use:**
        - High-stakes medical documents requiring verification
        - Training scenarios where you want to see AI reasoning
        - Quality assurance and auditing workflows
        """)

    st.markdown("---")

    # Info
    st.markdown("### Supported Documents")
    st.markdown("""
    - Prescriptions
    - Lab Reports
    - Medical Records
    """)

    st.markdown("---")

    st.markdown("### Platform Capabilities")
    st.markdown("""
    - Medical Classification
    - Clinical Data Extraction
    - Validation & Safety Alerts
    - HIPAA-Compliant Redaction
    - Audit Trail & Logging
    """)

    st.markdown("---")

    st.markdown("### Resources")
    st.markdown("[API Documentation](http://localhost:8000/docs)")

# Main Content
uploaded_file = st.file_uploader(
    "Upload Medical Document",
    type=['pdf'],
    help="Select a PDF file containing prescription, lab report, or medical record"
)

if uploaded_file is not None:
    # Initialize workflow state management
    if 'workflow_stage' not in st.session_state:
        st.session_state['workflow_stage'] = 'upload'
    if 'current_result' not in st.session_state:
        st.session_state['current_result'] = None
    if 'current_thread_id' not in st.session_state:
        st.session_state['current_thread_id'] = None

    # Reset workflow if file changed
    if 'last_filename' not in st.session_state:
        st.session_state['last_filename'] = uploaded_file.name
    elif st.session_state['last_filename'] != uploaded_file.name:
        st.session_state['workflow_stage'] = 'upload'
        st.session_state['current_result'] = None
        st.session_state['current_thread_id'] = None
        st.session_state['last_filename'] = uploaded_file.name

    # Display file info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Filename", uploaded_file.name)
    with col2:
        st.metric("File Size", f"{uploaded_file.size / 1024:.2f} KB")
    with col3:
        st.metric("Upload Time", datetime.now().strftime("%H:%M:%S"))

    st.markdown("---")

    # Process button - only triggers API call and updates state
    if st.button("Process Document", use_container_width=True):
        st.session_state['workflow_stage'] = 'processing'

        with st.spinner(f"Processing document with {llm_provider}..."):
            try:
                # Prepare file for upload
                files = {
                    "file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}

                # Add llm_provider as query parameter
                params = {"llm_provider": llm_provider.lower()}

                # Choose endpoint based on human review setting
                if enable_human_review:
                    endpoint = "http://localhost:8000/process/with-review"
                else:
                    endpoint = API_URL

                # Send request to API
                start_time = time.time()
                response = requests.post(
                    endpoint, files=files, params=params, timeout=300)
                end_time = time.time()

                if response.status_code == 200:
                    result = response.json()

                    # Update workflow state based on result
                    if enable_human_review and result.get("status") == "interrupted":
                        st.session_state['workflow_stage'] = 'interrupted'
                        st.session_state['current_result'] = result
                        st.session_state['current_thread_id'] = result.get(
                            'thread_id')
                    else:
                        st.session_state['workflow_stage'] = 'completed'
                        st.session_state['current_result'] = result

                    st.rerun()
                else:
                    st.error(f"API Error: {response.status_code}")
                    st.code(response.text)
                    st.session_state['workflow_stage'] = 'upload'

            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.session_state['workflow_stage'] = 'upload'

    # ===== HUMAN-IN-THE-LOOP: Handle Interrupt for Repair Review =====
    # This section is OUTSIDE the button block - triggered by workflow state
    if st.session_state.get('workflow_stage') == 'interrupted':
        result = st.session_state.get('current_result')
        thread_id = st.session_state.get('current_thread_id')

        if result and thread_id:
            # Clear visual section for review
            st.markdown("---")
            st.markdown("## ⏸️ PROCESSING PAUSED FOR HUMAN REVIEW")

            repair_summary = result.get("repair_summary", {})

            # Info box with thread details
            info_col1, info_col2 = st.columns([2, 1])
            with info_col1:
                st.info(
                    "🔍 The AI detected issues and applied automatic repairs. Please review the changes below.")
            with info_col2:
                st.caption(f"**Thread ID:** `{thread_id}`")

            st.markdown("---")

            # Display repair summary
            st.markdown("### 📋 Issues Detected and Repaired")

            flags_repaired = repair_summary.get("flags_repaired", [])
            if flags_repaired:
                st.markdown(f"**Issues Detected:** {len(flags_repaired)}")
                for flag in flags_repaired:
                    severity = flag.get("severity", "UNKNOWN")
                    severity_color = {
                        "CRITICAL": "🔴",
                        "HIGH": "🟠",
                        "MEDIUM": "🟡",
                        "LOW": "🟢"
                    }.get(severity, "⚪")

                    st.markdown(
                        f"{severity_color} **{flag.get('code')}** ({severity})")
                    st.markdown(f"  _{flag.get('message')}_")

            # Show LLM reasoning
            st.markdown("### 🤖 AI Reasoning")
            reasoning = repair_summary.get(
                "reasoning", "No reasoning provided")
            with st.container():
                st.markdown(f"""
                <div style="padding: 15px; background-color: #1e3a5f; border-left: 4px solid #3b82f6; border-radius: 5px;">
                    <p style="margin: 0; color: #e0e7ff;"><strong>Why the AI made these changes:</strong></p>
                    <p style="margin: 10px 0 0 0; color: #cbd5e1;">{reasoning}</p>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")

            # Side-by-side comparison
            st.markdown("### 📊 Before & After Comparison")
            st.caption("Review the original data vs. AI-suggested repairs")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### ❌ Original Data")
                st.caption("Data as extracted from the document")
                original_data = repair_summary.get("original_data", {})
                st.json(original_data)

            with col2:
                st.markdown("#### ✅ AI-Repaired Data")
                st.caption("Suggested corrections by the AI")
                repaired_data = repair_summary.get("repaired_data", {})
                st.json(repaired_data)

            st.markdown("---")

            # Human decision interface
            st.markdown("### 🧑‍⚕️ Your Decision")
            st.markdown("Choose how to proceed with the AI-suggested repairs:")

            decision_col1, decision_col2, decision_col3 = st.columns(3)

            with decision_col1:
                st.markdown("**✅ Accept AI Fix**")
                st.caption("Use the AI-corrected data and continue processing")
                approve_clicked = st.button(
                    "Approve Repair",
                    use_container_width=True,
                    type="primary",
                    key="approve_btn"
                )

            with decision_col2:
                st.markdown("**❌ Keep Original**")
                st.caption("Reject AI changes and use original data as-is")
                reject_clicked = st.button(
                    "Reject & Revert",
                    use_container_width=True,
                    key="reject_btn"
                )

            with decision_col3:
                st.markdown("**✏️ Custom Edit**")
                st.caption("Manually edit the data yourself")
                manual_override = st.button(
                    "Manual Override",
                    use_container_width=True,
                    key="override_btn"
                )

            # Handle approval
            if approve_clicked:
                with st.spinner("✅ Applying approved repairs and continuing processing..."):
                    try:
                        approval_response = requests.post(
                            "http://localhost:8000/repair/approve",
                            json={
                                "thread_id": thread_id,
                                "approved": True
                            },
                            timeout=300
                        )

                        if approval_response.status_code == 200:
                            final_result = approval_response.json()
                            # Update workflow state
                            st.session_state['workflow_stage'] = 'completed'
                            st.session_state['current_result'] = final_result
                            st.success(
                                "✅ Repair approved! Processing completed successfully.")
                            time.sleep(1)  # Brief pause to show message
                            st.rerun()  # Refresh to show final results
                        else:
                            st.error(
                                f"❌ Approval failed with status: {approval_response.status_code}")
                            st.code(approval_response.text)

                    except Exception as e:
                        st.error(f"❌ Error during approval: {str(e)}")

            # Handle rejection
            elif reject_clicked:
                with st.spinner("❌ Reverting to original data and continuing..."):
                    try:
                        rejection_response = requests.post(
                            "http://localhost:8000/repair/approve",
                            json={
                                "thread_id": thread_id,
                                "approved": False
                            },
                            timeout=300
                        )

                        if rejection_response.status_code == 200:
                            final_result = rejection_response.json()
                            # Update workflow state
                            st.session_state['workflow_stage'] = 'completed'
                            st.session_state['current_result'] = final_result
                            st.warning(
                                "⚠️ Repair rejected. Continued with original data.")
                            time.sleep(1)  # Brief pause to show message
                            st.rerun()  # Refresh to show final results
                        else:
                            st.error(
                                f"❌ Rejection failed with status: {rejection_response.status_code}")
                            st.code(rejection_response.text)

                    except Exception as e:
                        st.error(f"❌ Error during rejection: {str(e)}")

            # Handle manual override
            elif manual_override:
                # Set flag in session state to persist across reruns
                st.session_state['show_manual_override'] = True

            # Show manual override interface (persists via session state)
            if st.session_state.get('show_manual_override', False):
                st.markdown("---")
                st.markdown("#### ✏️ Manual Data Override")
                st.info(
                    "💡 **Instructions:** Edit the JSON data below with your corrections, then click 'Submit Override' to continue processing.")

                # Editable JSON text area
                manual_data_str = st.text_area(
                    "Edit Medical Data (JSON Format)",
                    value=json.dumps(repaired_data, indent=2),
                    height=400,
                    help="Modify the medication details, dosages, units, or any other fields as needed",
                    key="manual_data_editor"
                )

                col_submit, col_cancel = st.columns([1, 1])

                with col_submit:
                    submit_override = st.button(
                        "📤 Submit Override", use_container_width=True, type="primary", key="submit_override_btn")

                with col_cancel:
                    cancel_override = st.button(
                        "🔙 Cancel", use_container_width=True, key="cancel_override_btn")

                if cancel_override:
                    # Clear the manual override flag and return to decision screen
                    st.session_state['show_manual_override'] = False
                    st.rerun()

                if submit_override:
                    try:
                        # Validate JSON first
                        manual_data = json.loads(manual_data_str)

                        st.info(
                            "📝 JSON is valid. Applying your custom corrections...")

                        with st.spinner("⚙️ Processing with your manual override..."):
                            override_response = requests.post(
                                "http://localhost:8000/repair/approve",
                                json={
                                    "thread_id": thread_id,
                                    "approved": False,
                                    "modified_data": manual_data
                                },
                                timeout=300
                            )

                            if override_response.status_code == 200:
                                final_result = override_response.json()
                                # Clear manual override flag
                                st.session_state['show_manual_override'] = False
                                # Update workflow state
                                st.session_state['workflow_stage'] = 'completed'
                                st.session_state['current_result'] = final_result
                                st.success(
                                    "✅ Manual override applied successfully! Processing completed.")
                                time.sleep(1)  # Brief pause to show message
                                st.rerun()  # Refresh to show final results
                            else:
                                st.error(
                                    f"❌ Override failed with status: {override_response.status_code}")
                                st.code(override_response.text)

                    except json.JSONDecodeError as e:
                        st.error(f"❌ Invalid JSON format: {str(e)}")
                        st.warning(
                            "💡 Please check your JSON syntax. Make sure all brackets, quotes, and commas are correct.")
                    except Exception as e:
                        st.error(f"❌ Error during override: {str(e)}")

        st.stop()  # Stop here until user makes a decision

    # ===== RESULTS DISPLAY =====
    # This section is OUTSIDE the button block - triggered by workflow state
    if st.session_state.get('workflow_stage') == 'completed':
        result = st.session_state.get('current_result')

        if result:
            # Success message
            st.success(
                f"Document processed successfully in {result.get('latency_ms', 0) / 1000:.2f} seconds")

            # Metrics
            st.markdown("## Results Overview")

            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

            with metric_col1:
                st.metric(
                    "Document Type",
                    result.get('doc_type', 'Unknown').replace('_', ' ').title()
                )

            with metric_col2:
                # NEW: Display confidence score from structured output parser
                confidence = result.get('confidence_score', 0.0)
                confidence_pct = f"{confidence * 100:.0f}%" if confidence else "N/A"
                confidence_delta = None
                if confidence and confidence > 0.8:
                    confidence_delta = "High"
                elif confidence and confidence > 0.5:
                    confidence_delta = "Medium"
                elif confidence:
                    confidence_delta = "Low"

                st.metric(
                    "Confidence Score",
                    confidence_pct,
                    delta=confidence_delta
                )

            with metric_col3:
                st.metric(
                    "Processing Time",
                    f"{result.get('latency_ms', 0) / 1000:.2f}s"
                )

            with metric_col4:
                errors = result.get('errors', [])
                validation_flags = result.get('validation_flags', [])

                status = "Success"
                if errors:
                    status = "Error"
                elif fn := [f for f in validation_flags if f.get('severity') == 'CRITICAL']:
                    status = "Critical Alert"
                elif validation_flags:
                    status = "Warning"

                st.metric("Status", status)

            st.markdown("---")

            # Tabs for different views
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "Extracted Data",
                "Validation Alerts",
                "Redacted Text",
                "Metrics",
                "Agent Trace",
                "Raw Response"
            ])

            with tab1:
                st.markdown("### Validated Clinical Data")
                validated_data = result.get('validated_data', {})
                doc_type = result.get('doc_type', 'unknown')

                if validated_data:
                    if doc_type == 'prescription':
                        # Doctor Info
                        doc = validated_data.get('doctor', {})
                        st.markdown(
                            f"#### Prescriber: {doc.get('name', 'N/A')}")
                        st.write(
                            f"**License:** {doc.get('license_number', 'N/A')} | **DEA:** {doc.get('dea_number', 'N/A')}")

                        # Patient Info
                        pat = validated_data.get('patient', {})
                        st.markdown(
                            f"#### Patient: {pat.get('name', 'N/A')}")
                        st.write(
                            f"**Age:** {pat.get('age', 'N/A')} | **Weight:** {pat.get('weight', 'N/A')} kg | **Gender:** {pat.get('gender', 'N/A')}")

                        # Medications Table
                        meds = validated_data.get('medications', [])
                        if meds:
                            st.markdown("#### Medications")
                            import pandas as pd
                            med_df = pd.DataFrame(meds)
                            # Rename columns for display
                            med_df.columns = [
                                c.replace('_', ' ').title() for c in med_df.columns]
                            st.dataframe(med_df, use_container_width=True)

                        st.markdown(
                            f"**Diagnosis:** {validated_data.get('diagnosis', 'N/A')}")
                        st.markdown(
                            f"**Date:** {validated_data.get('date', 'N/A')}")

                    elif doc_type == 'lab_report':
                        # Lab Info
                        lab = validated_data.get('lab', {})
                        st.markdown(
                            f"#### Laboratory: {lab.get('name', 'N/A')}")
                        st.write(
                            f"**Report ID:** {validated_data.get('report_id', 'N/A')} | **Collection:** {validated_data.get('collection_date', 'N/A')} | **Report:** {validated_data.get('report_date', 'N/A')}")
                        if validated_data.get('is_amended'):
                            st.warning("This is an AMENDED report.")

                        # Patient Info
                        st.write(
                            f"**Patient ID:** {validated_data.get('patient_id', 'N/A')}")

                        # Results Table
                        results = validated_data.get('test_results', [])
                        if results:
                            st.markdown("#### Test Results")
                            import pandas as pd
                            res_df = pd.DataFrame(results)
                            # Format columns
                            res_df.columns = [
                                c.replace('_', ' ').title() for c in res_df.columns]
                            st.dataframe(res_df, use_container_width=True)

                    else:
                        # Fallback for other types
                        st.json(validated_data)
                else:
                    st.info("No structured data extracted")

            with tab2:
                st.markdown("### Clinical Validation Alerts")
                flags = result.get('validation_flags', [])
                if flags:
                    for flag in flags:
                        severity = flag.get('severity', 'LOW')
                        msg = f"**[{severity}]** {flag.get('message')}"
                        if severity == 'CRITICAL':
                            st.error(msg)
                        elif severity in ['HIGH', 'MEDIUM']:
                            st.warning(msg)
                        else:
                            st.info(msg)
                else:
                    st.success("No clinical alerts found.")

            with tab3:
                st.markdown("### PII-Redacted Text")
                redacted_text = result.get('redacted_text', '')

                if redacted_text:
                    st.text_area(
                        "Redacted Content",
                        redacted_text,
                        height=300,
                        label_visibility="collapsed"
                    )
                else:
                    st.info("No redacted text available")

            with tab4:
                st.markdown("### 📊 Reporter Metrics")

                # Extract reporter data from trace (or direct if available)
                # ... (existing reporter logic)
                metrics_file = result.get('metrics_file')  # If API returns it

                # Using trace to find reporter output
                reporter_data = None
                for step in result.get('trace', []):
                    if step.get('agent') == 'reporter':
                        reporter_data = step.get('metrics', {})
                        break

                if reporter_data:
                    # Extraction Metrics
                    st.markdown("#### 📋 Extraction Metrics")
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.metric(
                            "Extraction Completeness",
                            reporter_data.get('extraction_completeness', 'N/A')
                        )

                    with col2:
                        st.metric(
                            "Validation Accuracy",
                            reporter_data.get('validation_accuracy', 'N/A')
                        )

                    with col3:
                        pipeline_success = reporter_data.get(
                            'pipeline_success', False)
                        st.metric(
                            "Pipeline Status",
                            "Success" if pipeline_success else "Failed"
                        )

                    if not pipeline_success:
                        st.error("#### Pipeline Errors")
                        pipeline_errors = result.get('errors', [])
                        if pipeline_errors:
                            for err in pipeline_errors:
                                st.write(f"- {err}")
                        else:
                            st.write(
                                "No specific error messages found in trace, but success criteria not met.")

                    st.markdown("---")
                    st.markdown("#### PII Redaction Summary")
                    # ... (existing PII logic)

                    trace = result.get('trace', [])
                    pii_info = None
                    for step in trace:
                        if step.get('agent') == 'redactor':
                            pii_info = step
                            break

                    if pii_info:
                        pii_types = pii_info.get('pii_types_scrubbed', [])
                        if pii_types:
                            st.write(
                                f"**PII Types Redacted:** {', '.join(pii_types)}")
                        else:
                            st.info("No PII detected/redacted")
                else:
                    st.info("Reporter metrics not available")

            with tab5:
                st.markdown("### Agent Execution Trace")
                trace = result.get('trace', [])

                if trace:
                    for i, step in enumerate(trace, 1):
                        agent_name = step.get('agent', 'Unknown Agent')
                        status = step.get('status', 'unknown')

                        # Create status badge
                        status_emoji = {
                            'success': '✅',
                            'success_fallback': '⚠️',
                            'passed': '✅',
                            'completed': '✅',
                            'failed': '❌',
                            'skipped': '⏭️'
                        }.get(status, '❓')

                        with st.expander(f"{status_emoji} Step {i}: {agent_name.replace('_', ' ').title()} ({status})", expanded=(i == len(trace))):
                            # NEW: Highlight important info based on agent type
                            if 'classifier' in agent_name:
                                st.markdown("#### Classification Details")
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(
                                        f"**Output:** {step.get('output', 'N/A')}")
                                with col2:
                                    conf = step.get('confidence', 'N/A')
                                    if isinstance(conf, (int, float)):
                                        st.write(
                                            f"**Confidence:** {conf * 100:.1f}%")
                                    else:
                                        st.write(f"**Confidence:** {conf}")
                                st.write(
                                    f"**Model:** {step.get('model', 'N/A')}")
                                st.write(
                                    f"**Provider:** {step.get('provider', 'N/A')}")

                            elif 'extractor' in agent_name:
                                st.markdown("#### Extraction Details")
                                col1, col2 = st.columns(2)
                                with col1:
                                    conf = step.get('confidence', 'N/A')
                                    if isinstance(conf, (int, float)):
                                        st.write(
                                            f"**Confidence:** {conf * 100:.1f}%")
                                    else:
                                        st.write(f"**Confidence:** {conf}")
                                with col2:
                                    # NEW: Show which parser was used
                                    parser = step.get('parser', 'N/A')
                                    if parser == 'PydanticOutputParser':
                                        st.write(
                                            f"**Parser:** 🔒 {parser} (Validated)")
                                    elif parser == 'manual_json':
                                        st.write(
                                            f"**Parser:** ⚠️ {parser} (Fallback)")
                                    else:
                                        st.write(f"**Parser:** {parser}")

                                fields = step.get('fields_found', [])
                                if fields:
                                    st.write(
                                        f"**Fields Extracted:** {len(fields)}")
                                    st.write(", ".join(fields))

                            elif 'validator' in agent_name:
                                st.markdown("#### Validation Details")
                                flags_count = step.get('flags_generated', 0)
                                st.write(
                                    f"**Validation Flags:** {flags_count}")
                                st.write(
                                    f"**Schema:** {step.get('schema', 'N/A')}")

                            # Show full trace data
                            with st.expander("View Full Trace Data"):
                                st.json(step)
                else:
                    st.info("No trace information available")

            with tab6:
                st.markdown("### Complete API Response")
                st.json(result)

            # Errors section
            errors = result.get('errors', [])
            if errors:
                st.markdown("---")
                st.markdown("## System Errors")
                for error in errors:
                    st.error(error)

else:
    # Welcome screen
    st.markdown("---")
    st.info("Upload a medical document (PDF) to begin processing")

    st.markdown("## How It Works")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        ### Step 1: Upload
        Upload a prescription or lab report in PDF format
        """)

    with col2:
        st.markdown("""
        ### Step 2: Process
        AI agents classify, extract, validate and redact
        """)

    with col3:
        st.markdown("""
        ### Step 3: Results
        View clinical data, alerts, and metrics
        """)

    st.markdown("---")

    st.markdown("## Processing Pipeline")
    st.markdown("""
    ```
    Document Upload
         ↓
    Classifier Agent → Identifies document type
         ↓
    Extractor Agent → Extracts structured clinical data
         ↓
    Validator Agent → Validates safety and accuracy
         ↓
    Redactor Agent → Applies HIPAA-compliant redaction
         ↓
    Reporter Agent → Generates audit trail and metrics
         ↓
    Final Results
    ```
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #94a3b8; font-size: 13px; padding: 20px 0;'>
    Medical Document Intelligence Platform | Powered by LangGraph, FastAPI, and Streamlit<br>
    Multi-Provider LLM Support: Ollama, Groq, Amazon Bedrock
</div>
""", unsafe_allow_html=True)
