import streamlit as st
import hashlib
import os
import tempfile
import re
from io import BytesIO
from datetime import date
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from rag import (
    load_pdf,
    split_documents,
    create_embeddings,
    create_vector_store,
    create_llm,
    generate_answer,
    rewrite_question,
    compare_documents,
    validate_comparison_evidence
)

def create_pdf_report(comparison, filenames):
    buffer = BytesIO()

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(
        Paragraph("AI Document Assistant", styles["Title"])
    )
    story.append(
        Paragraph("Document Comparison Report", styles["Heading2"])
    )
    story.append(
        Paragraph(f"Generated: {date.today().strftime('%d %B %Y')}",
                  styles["Normal"])
    )
    story.append(Spacer(1, 12))

    story.append(Paragraph("Documents Compared", styles["Heading2"]))

    for filename in filenames:
        story.append(Paragraph(escape(filename), styles["Normal"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Comparison Results", styles["Heading2"]))

    # Render Markdown tables as actual PDF tables
    lines = comparison.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("|") and "|" in line[1:]:
            table_lines = []

            while i < len(lines) and lines[i].strip().startswith("|"):
                current = lines[i].strip()
                cells = [
                    cell.strip()
                    for cell in current.strip("|").split("|")
                ]

                # Skip Markdown separator rows, such as |---|---|
                if not all(
                    re.fullmatch(r":?-{3,}:?", cell.replace(" ", ""))
                    for cell in cells
                ):
                    table_lines.append(cells)

                i += 1

            if table_lines:
                column_count = max(len(row) for row in table_lines)
                table_data = []

                for row in table_lines:
                    row = row + [""] * (column_count - len(row))
                    table_data.append([
                        Paragraph(escape(cell), styles["BodyText"])
                        for cell in row
                    ])

                col_width = (A4[0] - 36 * mm) / column_count

                table = Table(
                    table_data,
                    colWidths=[col_width] * column_count,
                    repeatRows=1
                )

                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0),
                     colors.HexColor("#DCE6F1")),
                    ("TEXTCOLOR", (0, 0), (-1, 0),
                     colors.black),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))

                story.append(table)
                story.append(Spacer(1, 10))
            continue

        elif line:
            story.append(
                Paragraph(escape(line), styles["BodyText"])
            )
            story.append(Spacer(1, 5))

        i += 1

    pdf.build(story)
    buffer.seek(0)
    return buffer.getvalue()



st.markdown("""
<style>

/* ===== MAIN BACKGROUND ===== */
.stApp {
    background:
        radial-gradient(circle at 10% 10%, rgba(220, 25, 65, 0.22), transparent 30%),
        radial-gradient(circle at 90% 15%, rgba(90, 65, 220, 0.25), transparent 32%),
        radial-gradient(circle at 50% 100%, rgba(30, 100, 230, 0.18), transparent 40%),
        #090b14;
    color: #ffffff;
}

/* ===== SIDEBAR ===== */
[data-testid="stSidebar"] {
    background: linear-gradient(
        160deg,
        #210d1b,
        #11152c 55%,
        #0b1020
    );
    border-right: 1px solid rgba(150, 100, 255, 0.3);
}

/* ===== MAIN CONTENT ===== */
.block-container {
    max-width: 1200px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

/* ===== HEADINGS ===== */
h1, h2, h3 {
    color: #ffffff !important;
    font-weight: 750 !important;
}

p, label {
    color: #d4d5e8;
}

/* ===== GLOSSY HERO SECTION ===== */
.hero-panel {
    padding: 35px;
    margin-bottom: 30px;
    border-radius: 24px;
    background: linear-gradient(
        115deg,
        #79152f 0%,
        #243e99 52%,
        #642b9b 100%
    );
    border: 1px solid rgba(255,255,255,0.25);
    box-shadow:
        0 15px 45px rgba(0,0,0,0.4),
        inset 0 1px 0 rgba(255,255,255,0.25);
}

.hero-kicker {
    color: #e8dfff;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 3px;
    text-transform: uppercase;
}

.hero-title {
    color: white;
    font-size: 38px;
    font-weight: 850;
    margin: 10px 0;
    text-shadow: 0 3px 15px rgba(0,0,0,0.3);
}

.hero-subtitle {
    color: #e6e8ff;
    font-size: 16px;
}

/* ===== UPLOAD AND FORM PANELS ===== */
div[data-testid="stFileUploader"],
div[data-testid="stExpander"],
div[data-testid="stForm"] {
    background: linear-gradient(
        145deg,
        rgba(30, 31, 55, 0.95),
        rgba(15, 19, 37, 0.95)
    );
    border: 1px solid rgba(125, 110, 220, 0.35);
    border-radius: 16px;
    box-shadow: 0 8px 25px rgba(0,0,0,0.2);
}

/* ===== INPUT BOX ===== */
div[data-testid="stTextInput"] input {
    background: #101426;
    color: white;
    border: 1px solid #5265c9;
    border-radius: 12px;
}

div[data-testid="stTextInput"] input:focus {
    border-color: #a78bfa;
    box-shadow: 0 0 10px rgba(139,92,246,0.4);
}

/* ===== GLOSSY BUTTONS ===== */
.stButton > button,
.stDownloadButton > button,
div[data-testid="stFormSubmitButton"] > button {
    color: white;
    font-weight: 700;
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 12px;
    background: linear-gradient(
        105deg,
        #a51e48,
        #315bd8 52%,
        #7138b8
    );
    box-shadow:
        0 7px 22px rgba(75,65,190,0.3),
        inset 0 1px 0 rgba(255,255,255,0.2);
    transition: all 0.2s ease;
}

.stButton > button:hover,
.stDownloadButton > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-2px);
    border-color: white;
    box-shadow: 0 10px 30px rgba(110,75,220,0.45);
}

/* ===== MODE SELECTOR ===== */
div[role="radiogroup"] label {
    background: rgba(35, 38, 65, 0.85);
    border: 1px solid rgba(130,120,220,0.35);
    border-radius: 12px;
    padding: 9px 14px;
}

/* ===== ALERTS ===== */
[data-testid="stAlert"] {
    border-radius: 14px;
}

/* ===== DIVIDERS ===== */
hr {
    border-color: rgba(145,130,210,0.25);
}

</style>

<div class="hero-panel">
    <div class="hero-kicker">AI-Powered Document Workspace</div>
    <div class="hero-title">📄 AI Document Assistant</div>
    <div class="hero-subtitle">
        Chat with PDFs • Discover Insights • Compare Documents
    </div>
</div>
""", unsafe_allow_html=True)


#CHAT HISTORY 
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "current_pdf_hash" not in st.session_state:
    st.session_state.current_pdf_hash = None


@st.cache_resource
def process_pdfs(pdf_files, pdf_bundle_hash):
    all_documents = []
    all_chunks = []

    for filename, pdf_bytes in pdf_files:
        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".pdf",
                delete=False
            ) as temp_file:
                temp_file.write(pdf_bytes)
                temp_path = temp_file.name

            documents = load_pdf(
                temp_path,
                source_filename=filename
            )

            chunks = split_documents(documents)

            all_documents.extend(documents)
            all_chunks.extend(chunks)

        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    if not all_chunks:
        raise ValueError("No readable text found in the uploaded PDFs.")

    embeddings = create_embeddings()

    # One shared FAISS index for every uploaded PDF
    vector_store = create_vector_store(
        all_chunks,
        embeddings
    )

    return all_documents, all_chunks, vector_store



with st.sidebar:

    st.header("📄 Document")

    uploaded_files = st.file_uploader(
        "Upload your PDF",
        type=["pdf"],
        accept_multiple_files= True
    )

    st.divider()

    if st.session_state.chat_history:

        if st.button(
            "🗑️ Clear Conversation",
            use_container_width=True
        ):

            st.session_state.chat_history = []

            st.rerun()





if uploaded_files:
    pdf_files = tuple(
        (file.name, file.getvalue())
        for file in uploaded_files
    )

    # Create a hash for the complete uploaded document batch
    hasher = hashlib.md5()

    for filename, pdf_bytes in pdf_files:
        hasher.update(filename.encode("utf-8"))
        hasher.update(pdf_bytes)

    pdf_bundle_hash = hasher.hexdigest()

    if st.session_state.current_pdf_hash != pdf_bundle_hash:
        st.session_state.chat_history = []
        st.session_state.current_pdf_hash = pdf_bundle_hash

    st.subheader("📚 Your Documents")

    for filename, _ in pdf_files:
        st.write(f"📄 {filename}")

    try:
        documents, chunks, vector_store = process_pdfs(
            pdf_files,
            pdf_bundle_hash
        )
    except Exception as e:
        st.error("❌ Failed to process the uploaded PDFs.")
        st.caption(str(e))
        st.stop()

    if not documents:
        st.warning("No readable text was found.")
        st.stop()

    st.success(
        f"✅ Knowledge base ready: "
        f"{len(pdf_files)} PDF(s), "
        f"{len(documents)} page(s), "
        f"{len(chunks)} chunks."
    )

    



    # QUESTION INPUT
    
    mode = st.radio(
       "Choose a mode",
         ["💬 Ask Documents", "🔍 Compare Documents"],
         horizontal=True
        )

    with st.form("question_form"):
       if mode == "💬 Ask Documents":
        question = st.text_input(
            "Ask a question about your uploaded PDFs"
        )
       else:
        question = st.text_input(
            "What would you like to compare?",
            placeholder="e.g. What information is common between both documents?"
        )

       submitted = st.form_submit_button(
        "Ask" if mode == "💬 Ask Documents" else "Compare"
    )



    # PROCESS QUESTION

    if submitted and question:

       if mode == "💬 Ask Documents":

        with st.spinner("🤖 Thinking..."):
            llm = create_llm()

            search_question = rewrite_question(
                llm,
                question,
                st.session_state.chat_history
            )

            results_with_scores = (
                vector_store.similarity_search_with_score(
                    search_question,
                    k=3
                )
            )

            if not results_with_scores:
                st.warning("No relevant information was found.")
                st.stop()

            THRESHOLD = 1.6

            results = [
                doc
                for doc, score in results_with_scores
                if score <= THRESHOLD
            ]

            if not results:
                st.warning(
                    "I couldn't find this information in the uploaded PDFs."
                )
                st.stop()

            context = "\n\n".join(
                result.page_content for result in results
            )

            answer = generate_answer(
                llm,
                question,
                context
            )

        st.subheader("🤖 Answer")
        st.write(answer)

        with st.expander("📚 Sources"):
            grouped_sources = {}

            for result in results:
                filename = result.metadata.get(
                    "source_filename",
                    "Unknown document"
                )
                page_number = result.metadata.get("page", 0) + 1

                if filename not in grouped_sources:
                    grouped_sources[filename] = {}

                grouped_sources[filename][page_number] = (
                    result.page_content
                )

            for filename, pages in grouped_sources.items():
                st.markdown(f"### 📄 {filename}")

                for page_number, content in sorted(pages.items()):
                    st.markdown(f"**Page {page_number}**")
                    st.caption(content)

        st.session_state.chat_history.append({
            "question": question,
            "answer": answer
        })

    
       elif mode == "🔍 Compare Documents":

        if len(pdf_files) < 2:
            st.warning("Please upload at least two PDFs to compare.")
            st.stop()

        with st.spinner("🔍 Comparing documents..."):
            try:
                # Gather extracted text separately for each PDF
                document_texts = {}

                for document in documents:
                    filename = document.metadata.get(
                        "source_filename",
                        "Unknown document"
                    )

                    if filename not in document_texts:
                        document_texts[filename] = []

                    page_number = document.metadata.get("page", 0) + 1

                    document_texts[filename].append(
                      f"[Source: {filename}, Page: {page_number}]\n"
                      f"{document.page_content}"
)

                if len(document_texts) < 2:
                    st.error("Could not identify two separate documents.")
                    st.stop()

                filenames = list(document_texts.keys())

                document_a = "\n\n".join(document_texts[filenames[0]])
                document_b = "\n\n".join(document_texts[filenames[1]])

                llm = create_llm()

                comparison = compare_documents(
                    llm,
                    document_a,
                    document_b,
                    question
                )
                
                
                validation_results = validate_comparison_evidence(
    document_texts,
    comparison
)

                missing_files = [
                  filename
                  for filename, found in validation_results.items()
                  if not found
]

          

                if missing_files:
                   st.warning(
        "The comparison does not reference every uploaded document: "
        + ", ".join(missing_files)
    )
                else:
                  st.success("Both uploaded document filenames appear in the comparison.")

                if not comparison:
                    st.warning("The AI returned an empty comparison.")
                    st.stop()

                st.subheader("🔍 Comparison Results")
                comparison = comparison.replace("<br>", "\n")
                comparison = comparison.replace("<br/>", "\n")
                comparison = comparison.replace("<br />", "\n")

                
                st.markdown(
                    comparison,
                    unsafe_allow_html=False
)
                
                st.download_button(
                   label="📥 Download Comparison Report",
                   data=f"# Document Comparison Report\n\n"
                    f"**Documents compared:** {', '.join(document_texts.keys())}\n\n"
                    f"## Comparison Results\n\n{comparison}\n",
                  file_name="document_comparison_report.md",
                   mime="text/markdown",
                   key="download_markdown_report"
)
                pdf_report = create_pdf_report(
                   comparison,
                   list(document_texts.keys())
)

                st.download_button(
                   label="📄 Download PDF Report",
                   data=pdf_report,
                   file_name="document_comparison_report.pdf",
                   mime="application/pdf",
                   key="download_pdf_report"
)


                st.subheader("📚 Documents Compared")

                for filename, text_pages in document_texts.items():
                    st.markdown(f"- **{filename}**")

                st.caption(
                    "The comparison uses extracted text from both uploaded PDFs."
                )

                st.session_state.chat_history.append({
                    "question": question,
                    "answer": comparison
                })

            except Exception as e:
                st.error("Failed to compare documents.")
                st.exception(e)


   

  
if st.session_state.chat_history:

    st.subheader("💬 Conversation")

    for chat in st.session_state.chat_history:

        st.chat_message("user").write(
            chat["question"]
        )

        st.chat_message("assistant").write(
            chat["answer"]
        )

       