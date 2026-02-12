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
    - **Invoices** 📋
    - **ID Cards** 🪪
    - **Other Documents** 📄
    """)
    
    st.markdown("---")
    
    st.markdown("### 🤖 Features")
    st.markdown("""
    - Document Classification
    - Data Extraction
    - Schema Validation
    - Auto-Repair
    - PII Redaction
    """)
    
    st.markdown("---")
    
    st.markdown("### 🔗 Quick Links")
    st.markdown("[API Docs](http://localhost:8000/docs)")
    st.markdown("[GitHub](https://github.com)")

# Main Content
uploaded_file = st.file_uploader(
    "Upload a PDF document",
    type=['pdf'],
    help="Upload an invoice, ID card, or other document for processing"
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
                        st.metric(
                            "Status",
                            "✅ Success" if not errors else "⚠️ Warnings"
                        )
                    
                    st.markdown("---")
                    
                    # Tabs for different views
                    tab1, tab2, tab3, tab4, tab5 = st.tabs([
                        "📋 Extracted Data",
                        "🔒 Redacted Text",
                        "📊 Reporter Metrics",
                        "🔍 Agent Trace",
                        "📄 Raw Response"
                    ])
                    
                    with tab1:
                        st.markdown("### Validated Data")
                        validated_data = result.get('validated_data', {})
                        
                        if validated_data:
                            # Display as formatted key-value pairs
                            for key, value in validated_data.items():
                                col_a, col_b = st.columns([1, 2])
                                with col_a:
                                    st.markdown(f"**{key.replace('_', ' ').title()}:**")
                                with col_b:
                                    st.markdown(f"`{value}`")
                        else:
                            st.info("No structured data extracted")
                    
                    with tab2:
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
                    
                    with tab3:
                        st.markdown("### 📊 Reporter Metrics")
                        
                        # Extract reporter data from trace
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
                            
                            st.markdown("---")
                            
                            # Additional metrics from trace
                            trace = result.get('trace', [])
                            
                            # Count PII types redacted
                            pii_info = None
                            for step in trace:
                                if step.get('agent') == 'redactor':
                                    pii_info = step
                                    break
                            
                            if pii_info:
                                st.markdown("#### 🔒 PII Redaction")
                                pii_types = pii_info.get('pii_types_scrubbed', [])
                                if pii_types:
                                    st.write(f"**PII Types Redacted:** {', '.join(pii_types)}")
                                else:
                                    st.info("No PII detected in document")
                            
                            # Repair attempts
                            repair_attempts = result.get('trace', [{}])[-1].get('repair_attempts', 0)
                            if repair_attempts > 0:
                                st.markdown("---")
                                st.markdown("#### 🔧 Repair Metrics")
                                st.warning(f"⚠️ Document required {repair_attempts} repair attempt(s)")
                        
                        else:
                            st.info("Reporter metrics not available in this response")
                    
                    with tab4:
                        st.markdown("### Agent Execution Trace")
                        trace = result.get('trace', [])
                        
                        if trace:
                            for i, step in enumerate(trace, 1):
                                agent_name = step.get('agent', 'Unknown Agent')
                                
                                # Add emoji based on agent type
                                agent_emoji = {
                                    'classifier': '🔍',
                                    'extractor': '📝',
                                    'extractor_invoice': '📝',
                                    'extractor_id_card': '📝',
                                    'validator': '✅',
                                    'redactor': '🔒',
                                    'reporter': '📊'
                                }.get(agent_name, '🤖')
                                
                                with st.expander(f"Step {i}: {agent_emoji} {agent_name.replace('_', ' ').title()}", expanded=(i==len(trace))):
                                    st.json(step)
                        else:
                            st.info("No trace information available")
                    
                    with tab5:
                        st.markdown("### Complete API Response")
                        st.json(result)
                    
                    # Errors section
                    if errors:
                        st.markdown("---")
                        st.markdown("## ⚠️ Warnings/Errors")
                        for error in errors:
                            st.warning(error)
                
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
    st.info("👆 Upload a PDF document to get started")
    
    st.markdown("## 🎯 How It Works")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        ### 1️⃣ Upload
        Upload your PDF document (invoice, ID card, etc.)
        """)
    
    with col2:
        st.markdown("""
        ### 2️⃣ Process
        AI agents classify, extract, validate, and redact
        """)
    
    with col3:
        st.markdown("""
        ### 3️⃣ Results
        Get structured data and redacted text
        """)
    
    st.markdown("---")
    
    st.markdown("## 🔄 Processing Pipeline")
    st.markdown("""
    ```
    Document Upload
         ↓
    Classifier Agent → Identifies document type
         ↓
    Extractor Agent → Extracts key fields
         ↓
    Validator Agent → Validates against schema
         ↓
    Repair Agent → Fixes errors (if needed)
         ↓
    Redactor Agent → Masks PII
         ↓
    Reporter Agent → Generates metrics
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
