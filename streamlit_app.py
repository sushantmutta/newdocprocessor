import streamlit as st
import requests
import json
from datetime import datetime
import time

# Page Configuration
st.set_page_config(
    page_title="Agentic Document Processor",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme with readable fonts
st.markdown("""
    <style>
    /* Main background */
    .stApp {
        background-color: #1a1a1a;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #2d2d2d;
    }
    
    /* Text styling - medium, readable fonts */
    .stMarkdown, .stText, p, span, div {
        color: #e0e0e0 !important;
        font-size: 16px !important;
        line-height: 1.6 !important;
    }
    
    /* Headers */
    h1 {
        color: #ffffff !important;
        font-size: 42px !important;
        font-weight: 600 !important;
        margin-bottom: 20px !important;
    }
    
    h2 {
        color: #f0f0f0 !important;
        font-size: 32px !important;
        font-weight: 500 !important;
        margin-top: 30px !important;
    }
    
    h3 {
        color: #e0e0e0 !important;
        font-size: 24px !important;
        font-weight: 500 !important;
    }
    
    /* File uploader */
    [data-testid="stFileUploader"] {
        background-color: #2d2d2d;
        border: 2px dashed #4a9eff;
        border-radius: 10px;
        padding: 20px;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #4a9eff;
        color: white;
        font-size: 18px !important;
        font-weight: 500;
        padding: 12px 30px;
        border-radius: 8px;
        border: none;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        background-color: #357abd;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(74, 158, 255, 0.4);
    }
    
    /* Success/Error/Info boxes */
    .stSuccess {
        background-color: #1e4620;
        color: #90ee90 !important;
        font-size: 16px !important;
        border-left: 4px solid #4caf50;
        padding: 15px;
        border-radius: 5px;
    }
    
    .stError {
        background-color: #4a1e1e;
        color: #ff9999 !important;
        font-size: 16px !important;
        border-left: 4px solid #f44336;
        padding: 15px;
        border-radius: 5px;
    }
    
    .stInfo {
        background-color: #1e3a4a;
        color: #90d5ff !important;
        font-size: 16px !important;
        border-left: 4px solid #2196f3;
        padding: 15px;
        border-radius: 5px;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: 28px !important;
        color: #4a9eff !important;
        font-weight: 600 !important;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 16px !important;
        color: #b0b0b0 !important;
    }
    
    /* JSON viewer */
    .stJson {
        background-color: #2d2d2d;
        border-radius: 8px;
        padding: 15px;
        font-size: 15px !important;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: #2d2d2d;
        color: #e0e0e0 !important;
        font-size: 18px !important;
        font-weight: 500;
        border-radius: 8px;
    }
    
    /* Code blocks */
    code {
        background-color: #2d2d2d;
        color: #4a9eff !important;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 15px !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #2d2d2d;
        color: #b0b0b0;
        font-size: 16px !important;
        padding: 10px 20px;
        border-radius: 8px 8px 0 0;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #4a9eff;
        color: white !important;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-top-color: #4a9eff !important;
    }
    
    /* Dataframe */
    .dataframe {
        font-size: 15px !important;
        color: #e0e0e0 !important;
    }
    </style>
""", unsafe_allow_html=True)

# API Configuration
API_URL = "http://localhost:8000/process"

# Header
st.title("📄 Agentic Document Processor")
st.markdown("### Intelligent document classification, extraction, validation, and redaction powered by LangGraph")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # API Status Check
    try:
        response = requests.get("http://localhost:8000/docs", timeout=2)
        if response.status_code == 200:
            st.success("✅ API Server: Online")
        else:
            st.error("❌ API Server: Offline")
    except:
        st.error("❌ API Server: Not Running")
        st.info("Start the server:\n```bash\npython -m uvicorn api:api --host 127.0.0.1 --port 8000\n```")
    
    st.markdown("---")
    
    # LLM Provider Selection
    st.markdown("### 🤖 LLM Provider")
    
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
            st.success(f"✅ Groq API Key loaded from .env")
        else:
            st.warning("⚠️ GROQ_API_KEY not found in .env file")
            st.info("Add your Groq API key to .env file: GROQ_API_KEY=your_key_here")
    
    elif llm_provider == "Bedrock":
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        aws_region = os.getenv("AWS_REGION", "us-east-1")
        
        if aws_access_key and aws_secret_key:
            st.success("✅ AWS credentials loaded from .env")
        else:
            st.warning("⚠️ AWS credentials not found in .env file")
            st.info("Add AWS credentials to .env file")
    
    else:  # Ollama
        st.info("Using local Ollama instance at http://localhost:11434")
    
    st.markdown("---")
    
    # Info
    st.markdown("### 📊 Supported Documents")
    st.markdown("""
    - **Prescriptions** 💊
    - **Lab Reports** 🧪
    - **Other Medical Docs** 📄
    """)
    
    st.markdown("---")
    
    st.markdown("### 🤖 Features")
    st.markdown("""
    - **Medical Classification** (Rx vs Lab)
    - **Clinical Data Extraction**
    - **Validation & Alerts** (Critical Values, Drug Interactions)
    - **HIPAA-Compliant Redaction**
    - **Responsible AI Logging**
    """)
    
    st.markdown("---")
    
    st.markdown("### 🔗 Quick Links")
    st.markdown("[API Docs](http://localhost:8000/docs)")
    st.markdown("[GitHub](https://github.com)")

# Main Content
uploaded_file = st.file_uploader(
    "Upload a Medical Document (PDF)",
    type=['pdf'],
    help="Upload a Prescription, Lab Report, or other medical record"
)

if uploaded_file is not None:
    # Display file info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📄 Filename", uploaded_file.name)
    with col2:
        st.metric("📦 Size", f"{uploaded_file.size / 1024:.2f} KB")
    with col3:
        st.metric("📅 Uploaded", datetime.now().strftime("%H:%M:%S"))
    
    st.markdown("---")
    
    # Process button
    if st.button("🚀 Process Document", use_container_width=True):
        with st.spinner(f"🔄 Processing document with {llm_provider}... This may take a few moments."):
            try:
                # Prepare file for upload
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                
                # Add llm_provider as query parameter
                params = {"llm_provider": llm_provider.lower()}
                
                # Send request to API
                start_time = time.time()
                response = requests.post(API_URL, files=files, params=params, timeout=300)
                end_time = time.time()
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Success message
                    st.success(f"✅ Document processed successfully in {result.get('latency_ms', 0) / 1000:.2f} seconds!")
                    
                    # Metrics
                    st.markdown("## 📊 Results")
                    
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    
                    with metric_col1:
                        st.metric(
                            "Document Type",
                            result.get('doc_type', 'Unknown').replace('_', ' ').title()
                        )
                    
                    with metric_col2:
                        st.metric(
                            "Processing Time",
                            f"{result.get('latency_ms', 0) / 1000:.2f}s"
                        )
                    
                    with metric_col3:
                        errors = result.get('errors', [])
                        validation_flags = result.get('validation_flags', [])
                        
                        status = "✅ Success"
                        if errors:
                            status = "❌ Errors"
                        elif fn := [f for f in validation_flags if f.get('severity') == 'CRITICAL']:
                            status = "🚨 Critical Alerts"
                        elif validation_flags:
                            status = "⚠️ Warnings"
                            
                        st.metric("Status", status)
                    
                    st.markdown("---")
                    
                    # Tabs for different views
                    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                        "📋 Extracted Data",
                        "⚠️ Validation Alerts",
                        "🔒 Redacted Text",
                        "📊 Reporter Metrics",
                        "🔍 Agent Trace",
                        "📄 Raw Response"
                    ])
                    
                    with tab1:
                        st.markdown("### Validated Clinical Data")
                        validated_data = result.get('validated_data', {})
                        doc_type = result.get('doc_type', 'unknown')
                        
                        if validated_data:
                            if doc_type == 'prescription':
                                # Doctor Info
                                doc = validated_data.get('doctor', {})
                                st.markdown(f"#### 👨‍⚕️ Prescriber: {doc.get('name', 'N/A')}")
                                st.write(f"**License:** {doc.get('license_number', 'N/A')} | **DEA:** {doc.get('dea_number', 'N/A')}")
                                
                                # Patient Info
                                pat = validated_data.get('patient', {})
                                st.markdown(f"#### 👤 Patient: {pat.get('name', 'N/A')}")
                                st.write(f"**Age:** {pat.get('age', 'N/A')} | **Weight:** {pat.get('weight', 'N/A')} kg | **Gender:** {pat.get('gender', 'N/A')}")
                                
                                # Medications Table
                                meds = validated_data.get('medications', [])
                                if meds:
                                    st.markdown("#### 💊 Medications")
                                    import pandas as pd
                                    med_df = pd.DataFrame(meds)
                                    # Rename columns for display
                                    med_df.columns = [c.replace('_', ' ').title() for c in med_df.columns]
                                    st.dataframe(med_df, use_container_width=True)
                                
                                st.markdown(f"**Diagnosis:** {validated_data.get('diagnosis', 'N/A')}")
                                st.markdown(f"**Date:** {validated_data.get('date', 'N/A')}")

                            elif doc_type == 'lab_report':
                                # Lab Info
                                lab = validated_data.get('lab', {})
                                st.markdown(f"#### 🧪 Lab: {lab.get('name', 'N/A')}")
                                st.write(f"**Report ID:** {validated_data.get('report_id', 'N/A')} | **Collection:** {validated_data.get('collection_date', 'N/A')} | **Report:** {validated_data.get('report_date', 'N/A')}")
                                if validated_data.get('is_amended'):
                                    st.warning("⚠ This is an AMENDED report.")

                                # Patient Info
                                st.write(f"**Patient ID:** {validated_data.get('patient_id', 'N/A')}")

                                # Results Table
                                results = validated_data.get('test_results', [])
                                if results:
                                    st.markdown("#### 📋 Test Results")
                                    import pandas as pd
                                    res_df = pd.DataFrame(results)
                                    # Format columns
                                    res_df.columns = [c.replace('_', ' ').title() for c in res_df.columns]
                                    st.dataframe(res_df, use_container_width=True)
                            
                            else:
                                # Fallback for other types
                                st.json(validated_data)
                        else:
                            st.info("No structured data extracted")

                    with tab2:
                        st.markdown("### ⚠️ Clinical Validation Alerts")
                        flags = result.get('validation_flags', [])
                        if flags:
                            for flag in flags:
                                severity = flag.get('severity', 'LOW')
                                msg = f"**[{severity}]** {flag.get('message')}"
                                if severity == 'CRITICAL':
                                    st.error(msg, icon="🚨")
                                elif severity in ['HIGH', 'MEDIUM']:
                                    st.warning(msg, icon="⚠️")
                                else:
                                    st.info(msg, icon="ℹ️")
                        else:
                            st.success("✅ No clinical alerts found.")
                    
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
                        metrics_file = result.get('metrics_file') # If API returns it
                        
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
                                pipeline_success = reporter_data.get('pipeline_success', False)
                                st.metric(
                                    "Pipeline Status",
                                    "✅ Success" if pipeline_success else "❌ Failed"
                                )
                            
                            if not pipeline_success:
                                st.error("#### ⚠️ Pipeline Errors")
                                pipeline_errors = result.get('errors', [])
                                if pipeline_errors:
                                    for err in pipeline_errors:
                                        st.write(f"- {err}")
                                else:
                                    st.write("No specific error messages found in trace, but success criteria not met.")
                            
                            st.markdown("---")
                            st.markdown("#### 🔒 PII Redaction")
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
                                    st.write(f"**PII Types Redacted:** {', '.join(pii_types)}")
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
                                
                                # Add emoji based on agent type
                                agent_emoji = {
                                    'classifier': '🔍',
                                    'extractor': '📝',
                                    'extractor_prescription': '💊',
                                    'extractor_lab_report': '🧪',
                                    'validator': '✅',
                                    'redactor': '🔒',
                                    'reporter': '📊'
                                }.get(agent_name, '🤖')
                                
                                with st.expander(f"Step {i}: {agent_emoji} {agent_name.replace('_', ' ').title()}", expanded=(i==len(trace))):
                                    st.json(step)
                        else:
                            st.info("No trace information available")
                    
                    with tab6:
                        st.markdown("### Complete API Response")
                        st.json(result)
                    
                    # Errors section
                    if errors:
                        st.markdown("---")
                        st.markdown("## ⚠️ System Errors")
                        for error in errors:
                            st.error(error)
                
                else:
                    st.error(f"❌ Error: {response.status_code} - {response.text}")
            
            except requests.exceptions.Timeout:
                st.error("❌ Request timed out. The document may be too large or the server is busy.")
            
            except requests.exceptions.ConnectionError:
                st.error("❌ Could not connect to API server. Make sure it's running on http://localhost:8000")
            
            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")

else:
    # Welcome screen
    st.markdown("---")
    st.info("👆 Upload a Medical PDF (Prescription or Lab Report) to get started")
    
    st.markdown("## 🎯 How It Works")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        ### 1️⃣ Upload
        Upload a Prescription or Lab Report (PDF)
        """)
    
    with col2:
        st.markdown("""
        ### 2️⃣ Process
        AI Agents Classify, Extract, Validate & Redact
        """)
    
    with col3:
        st.markdown("""
        ### 3️⃣ Results
        View Clinical Data, Critical Alerts & Metrics
        """)
    
    st.markdown("---")
    
    st.markdown("## 🔄 Responsible AI Pipeline")
    st.markdown("""
    ```
    Document Upload
         ↓
    Classifier Agent → Distinguishes Prescription vs Lab Report
         ↓
    Extractor Agent → Extracts structured clinical data
         ↓
    Validator Agent → Checks Safety (Interactons, Dosages, Critical Values)
         ↓
    Redactor Agent → Masks HIPAA PII (SSN, MRN, Names)
         ↓
    Reporter Agent → Generates Trace & Compliance Metrics
         ↓
    Final Results
    ```
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #808080; font-size: 14px;'>
    Built with ❤️ using LangGraph, FastAPI, and Streamlit | 
    Multi-Provider LLM Support (Ollama, Groq, Bedrock)
</div>
""", unsafe_allow_html=True)
