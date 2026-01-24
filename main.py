import streamlit as st
import sys
import os
from dotenv import load_dotenv
load_dotenv()
from core.logger import get_logger
from app.file_utils import pdf_generator, file_parser
from app.email_utils.gmail_sender import send_email_with_attachment
from app.agents import ResumeAgent, CoverLetterAgent, EmailAgent
from pathlib import Path

st.set_page_config(
    page_title="GenApply - Job applications, personalized and sent in seconds",
    layout="wide"
)
st.title("GenApply - Job applications, personalized and sent instantly using AI")

st.markdown(
    """
    <style>
        /* Keep title centered globally */
        h1 {
            text-align: center !important;
            margin-left: 0 !important;
        }

        /* Center all app content */
        .block-container {
            display: flex;
            flex-direction: column;
            align-items: center;      /* centers horizontally */
            justify-content: center;  /* centers vertically if needed */
            text-align: center;       /* centers labels and small text */
            max-width: 500px;         /* semicolon added */
            margin: 0 auto;           /* semicolon added */
            padding-top: 1rem;
            padding-bottom: 2rem;
        }

        /* Make all inputs full width within the centered container */
        .stTextInput > div > div > input,
        .stTextArea > div > textarea,
        .stFileUploader > div > div > div > button,
        .stButton > button {
            width: 100%;              /* semicolon added */
        }

        /* Optional: shrink text area height slightly */
        textarea {
            min-height: 120px;        /* semicolon added */
        }

        /* Center checkboxes and labels */
        .stCheckbox {
            display: flex;
            justify-content: center;
        }

        /* Ensure buttons are side-by-side and centered */
        .stButton {
            display: inline-block;    /* semicolon added */
            margin: 0 10px;           /* semicolon added */
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# Inputs

# ----------------------------------------
# Setup
# ----------------------------------------

logger = get_logger(__name__)

# ----------------------------------------
# Streamlit UI
# ----------------------------------------


resume_file = st.file_uploader("Upload your LaTeX resume file (.tex or .txt)", type=["tex", "txt"])
job_role = st.text_input("Enter the Job Role you're applying for")
company_name = st.text_input("Enter the Company Name")
receiver_email = st.text_input("Recruiter/Company Email")
job_description = st.text_area("Paste the Job Description")
generate_cover_letter = st.checkbox("Generate Cover Letter", value=True)

# Placeholder paths

if "refined_resume_path" not in st.session_state:
    st.session_state.refined_resume_path = None
if "refined_cover_letter_path" not in st.session_state:
    st.session_state.refined_cover_letter_path = None



# ----------------------------------------
# Step 1: Generate Resume + Cover Letter
# ----------------------------------------
if st.button("Generate"):

    if not resume_file or not job_description or not receiver_email:
        st.warning("Please upload your resume, enter the job description, and provide your email address.")
        st.stop()

    try:       
        uploads_dir = os.getenv("UPLOADS_DIR", "data/uploads")  
        Path(uploads_dir).mkdir(parents=True, exist_ok=True)  
        temp_resume_path = Path(uploads_dir) / resume_file.name

        # Save uploaded file
        with open(temp_resume_path, "wb") as f:
            f.write(resume_file.getbuffer())
     
        # --- Generate Resume ---
        resume_status = st.empty()
        resume_status = st.info("Generating refined resume using AI...")

        resume_agent = ResumeAgent(
            resume_file=str(temp_resume_path),
            job_role=job_role,
            job_description=job_description
        )
        refined_resume = resume_agent.run()

        if refined_resume.get("status") == "success":
            resume_status.empty()
            refined_resume_path  = refined_resume.get("path")
            st.session_state["refined_resume_path"] = refined_resume_path
            st.success(f"Resume Generated: `{refined_resume_path}`. Please review before sending.")
        else:
            st.error("Resume generation failed.")
            st.stop()

        # --- Generate Cover Letter (Optional) ---
        if generate_cover_letter:
            cover_letter_status = st.empty()
            cover_letter_status = st.info("Generating cover letter using AI...")

            cover_letter_agent = CoverLetterAgent(
                refined_resume_path=st.session_state["refined_resume_path"],
                job_role=job_role,
                job_description = job_description,
                company=company_name
            )
            refined_cover = cover_letter_agent.run()

            if refined_cover.get("status") == "success":
                cover_letter_status.empty()
                refined_cover_letter_path = refined_cover.get("path")
                st.session_state["refined_cover_letter_path"] = refined_cover_letter_path
                st.success(f"Cover Letter Generated: `{refined_cover_letter_path}`. Please review before sending.")
            else:
                st.error("Cover letter generation failed.")

    except Exception as e:
        logger.error(f"Error during generation: {e}", exc_info=True)
        st.error("An unexpected error occurred during generation. Please check logs and retry.")
        st.stop()

# ----------------------------------------
# Step 2: Send Application
# ----------------------------------------
st.session_state["refined_resume_path"] = "data/resume/resume_20251021_063046.pdf"
st.session_state["refined_cover_letter_path"] = "data/cover_letter/cover_letter_20251021_063119.pdf"
if st.button("Send Application"):
    refined_resume_path = st.session_state["refined_resume_path"]
    refined_cover_letter_path = st.session_state["refined_cover_letter_path"]

    if not refined_resume_path or not os.path.exists(refined_resume_path):
        st.warning("Resume file not found. Please generate it first.")
        st.stop()

    try:
        attach_cover_letter = bool(refined_cover_letter_path and os.path.exists(refined_cover_letter_path))

        st.info("Sending application email...")

        email_agent = EmailAgent(
            resume_path=refined_resume_path,
            position=job_role,
            job_description=job_description,
            company=company_name,
            receiver_email=receiver_email,
            attach_cover_letter=attach_cover_letter,
            cover_letter_path=refined_cover_letter_path
        )
        email_status = email_agent.run()

        # --- Result ---
        if isinstance(email_status, dict) and email_status.get("status") == "success":
            st.success("Application sent successfully!")
        else:
            st.error(f"Failed to send email: {email_status}")

    except Exception as e:
        logger.error(f"Error sending email: {e}", exc_info=True)
        st.error("Failed to send the application. Please retry later.")
